# Agent Architecture

This document explains the tender response design in plain language.

You don't need to know LangGraph to follow it. The goal is to make the system shape obvious: what the workflow is trying to do, how work moves through it, where parallelism happens, and why the pipeline is split into specialized stages instead of one large prompt.

For the retrieval design, see [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md).
For state and memory, see [MEMORY_AND_STATE.md](./MEMORY_AND_STATE.md).

---

## Design Goal

The service receives a tender questionnaire, retrieves historical evidence, generates one response per question, and returns a structured batch result.

Four requirements shaped the design:

- each question must be processed independently so one failure doesn't block the batch
- answers must stay aligned with historical positioning
- the workflow needs short-term state during a run and shared memory across a session
- the final batch must be reviewed for contradictions across answers

That's why the workflow is a graph rather than a request-response chain.

---

## Workflow Overview

There are two layers:

1. a batch graph for the uploaded questionnaire
2. a per-question subgraph for each tender question

The batch graph owns the file. The per-question graph owns one question at a time.

### Batch Graph

```text
START
  -> dispatch_questions
  -> process_question (fan-out in parallel)
  -> prepare_conflict_review
  -> review_conflict_group (fan-out in parallel)
  -> apply_conflicts
  -> summarize_batch
  -> END
```

- `dispatch_questions` — turns the questionnaire into one unit of work per question
- `process_question` — runs the full per-question subgraph; each question is isolated
- `prepare_conflict_review` — waits until all questions finish, then collects completed answers and session memory
- `review_conflict_group` — checks whether answers contradict each other; runs in parallel over batches of target questions
- `apply_conflicts` — validates and writes conflict findings back to the affected answers
- `summarize_batch` — produces the final counts and overall completion status

### Per-Question Graph

```text
retrieve_alignment
  -> assess_references
  -> generate_answer or finalize_unanswered
  -> assess_output
  -> retry generate_answer up to 3 times if recoverable
  -> fail_generation or completed result
```

In plain language: find the best historical evidence, decide whether it's good enough to answer from, generate an answer if it is, validate that answer, and retry with feedback if it's fixable. If evidence is insufficient, return `unanswered` rather than guessing. If retries are exhausted, mark only that question as `failed`.

This is the key reason one broken answer doesn't break the whole run.

---

## Where Parallelism Happens

### Question Processing

After upload parsing, the batch graph fans out one `process_question` task per tender question. Question `q-001` doesn't wait for `q-002`. Slow or failed questions don't block already-finished ones. This is the main throughput gain.

### Conflict Review

Once question processing finishes, conflict review runs in parallel over groups of up to 10 completed answers. Each job checks its target questions against the full completed answer set for the session — session-wide coverage, not just local pair comparisons.

---

## Why A Graph And Not A Single Prompt

One large prompt could handle retrieval, grounding, generation, validation, retry, and conflict review — but it would blur all those responsibilities together.

The graph keeps them separate. Each stage has a clear purpose, failure handling is explicit, retry is controlled by state rather than hidden inside a long prompt, and session memory can be reused across requests. The individual stages are also easier to test and type-check because the contracts between them are explicit.

---

## Agent Responsibilities

Each agent is a runtime role with a narrow responsibility. It reads from a specific part of state and writes its result back into it.

### Retriever

The retriever finds the best historical evidence for the current question. Retrieval is intentionally a separate stage from generation: the workflow answers from stored evidence, not from model memory. It searches both `qa_records` and `document_records`, scores and merges the results, and passes a ranked reference list to the assessor. The full retrieval design is in [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md).

### Grounding Assessor

The grounding assessor decides whether the retrieved evidence is sufficient for a safe answer. Relevance is not the same as answerability: some questions are fully supported, some only partially, and some shouldn't be answered at all. The assessor produces one of four outcomes — `grounded`, `partial_reference`, `insufficient_reference`, or `no_reference` — which determines whether the workflow proceeds to generation or routes to an unanswered result.

### Answer Composer

The answer composer generates the response text and attached metadata: confidence level, risk level, and an inconsistency signal. It receives the current question, the usable references, the assessment reason, and any retry feedback from a previous failed attempt. It's a separate stage from grounding because answer writing is a different job from evidence qualification, and because the system needs both human-readable prose and machine-readable review signals in the output.

### Risk Guard

The risk guard validates the generated answer before it's accepted. Generation alone isn't sufficient — the workflow must block overclaims, malformed partial answers, and inconsistent wording. Specifically, it enforces that partial answers disclose missing scope, that partial answers reduce confidence appropriately, that unsupported claims don't pass through, and that absolute claims aren't weakened by caveats added afterward. Recoverable issues trigger a retry with feedback; three failed attempts mark the question as `failed`.

### Conflict Reviewer

The conflict reviewer checks whether completed answers contradict each other across the session. Answers can look fine in isolation and still conflict at batch level. It reviews only completed answers with displayable text, compares the current batch against any prior completed answers from the same session, and runs in parallel over grouped targets. Findings are validated before being written back to the affected questions.

---

## State And Memory

The state and memory design is covered in detail in [MEMORY_AND_STATE.md](./MEMORY_AND_STATE.md). The short version:

- **Per-question state** is the working memory for one question — references, assessment, answer draft, retry count, last error. It's created fresh per question and discarded when the question finishes.
- **Batch state** accumulates all question results, holds session memory from prior requests, and tracks conflict findings across the whole uploaded file.
- **Session memory** (`session_completed_results`) carries completed answers across multiple uploads in the same session, which is what makes cross-upload conflict review possible.

---

## Safety And Failure Model

The system fails conservatively.

- insufficient evidence returns `unanswered` rather than a guess
- retry is bounded — three failed attempts marks a question as `failed`, not stuck
- per-question isolation means one failure doesn't affect others
- post-batch conflict review catches contradictions that look fine per-question
- high-risk and inconsistency flags are surfaced in the final response

The system prefers partial but honest answers over confident ones it can't support.

---

## Why This Qualifies As Multi-Agent

The design is multi-agent because the workflow is intentionally split into specialized decision-makers, each with a distinct responsibility, explicit state inputs and outputs, and a clear place in the graph.

The point isn't the number of model calls. It's that retrieval, grounding, composition, validation, and conflict review are separate runtime roles with explicit handoffs between them. That separation of concerns is the core design principle.
