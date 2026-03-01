# Memory and State Design

This document explains how state and memory work in the tender-response workflow.

It is written to be readable without prior LangGraph knowledge. The goal is to make clear what the system remembers, for how long, and why each memory layer exists.

For the retrieval design that underpins long-term memory, see [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md).
For the agent roles that read and write this state, see [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md).

---

## The Core Idea

The workflow needs to hold information at three different timescales:

- **during a single generation attempt** — what was the last failed answer, why did it fail, how many retries have happened
- **across an entire session** — what has already been answered this session, do any new answers conflict with earlier ones
- **across all time** — what has the organisation approved and said in past tenders

Each timescale has a different mechanism. None of them are the same thing.

---

## State-Driven Design

LangGraph works by passing an explicit state object through the workflow. Every node reads from that state and writes its result back into it. No node has hidden inputs or side channels.

This means the workflow is fully traceable: at any point in the graph, the current state describes exactly where the system is and what it knows. Routing decisions — which node runs next — are made by inspecting that state, not by external logic.

There are two state scopes in this system.

### Per-Question State

When a question enters the workflow, it gets its own isolated working state. That state tracks everything the workflow needs to process that one question:

- the retrieved historical references
- the grounding assessment result
- the generated answer draft
- how many generation attempts have happened
- what went wrong in the last attempt, if anything
- the final result

This state is created fresh for every question. Nothing from one question leaks into another. A question that retries three times before failing does not slow down or affect the question running beside it.

### Batch State

Above the per-question level, there is a shared state for the entire uploaded file. It accumulates all question results as they finish, holds the session memory loaded from prior requests, and tracks any conflict findings or errors at the batch level.

Custom merge functions handle the case where multiple questions finish at the same time and both try to write their results. The merge is safe: results are combined by question ID rather than overwritten.

---

## Dynamic Processing

The workflow does not hard-code any question limit. When a file is uploaded, the graph reads the parsed question list and fans out one parallel branch per question. Ten questions produce ten parallel branches. Twenty produce twenty.

Each branch runs the full per-question workflow independently. As each branch finishes, its result is merged into the shared batch state. The graph waits until all branches complete before moving to conflict review.

If the uploaded file contains no questions, the workflow routes directly to the summary step and still returns a well-formed response.

---

## Conditional Branching: No Historical Match vs Historical Match

After the retriever finds historical evidence for a question, the workflow makes an explicit decision before attempting to generate an answer.

The decision is based on whether the retrieved evidence is actually usable:

**If usable evidence exists**, the question proceeds to answer generation. The workflow uses that evidence as the grounding source for the answer.

**If no usable evidence exists**, the question is marked as unanswered without attempting generation. The reason is recorded in the response.

The reasons a question may not proceed to generation:

| Grounding Status | Meaning |
|---|---|
| `grounded` | Full historical coverage. Answer generated. |
| `partial_reference` | Partial coverage. Answer generated with scope disclosure. |
| `no_reference` | No historical match found. Not answered. |
| `insufficient_reference` | References found but not safe to answer from. Not answered. |
| `conflict` | References contradict each other. Flagged for human review. |

An unanswered question is not a failure. It is an honest result: the system does not generate an answer it cannot support. The question receives a complete structured response with a status, a grounding status, and an explanation.

---

## Per-Question State and Shared Session Memory

These two things are separate by design.

### Per-Question

Each question's working state is isolated. When a question finishes, only the final result is promoted to the shared batch state. The intermediate details — alignment data, assessment reasoning, retry history — stay within that question's scope and are then discarded.

The retry history does appear in the final response output as an `extensions` field, so the reasoning trace is auditable after the fact even though it does not live in shared state.

### Shared Session Memory

`session_completed_results` is the memory that crosses question and request boundaries within one session.

Within a single run, conflict review uses it to compare answers against each other. A question answered in position 5 can be checked for contradictions against a question answered in position 12.

Across multiple requests with the same session ID, it carries completed answers forward. If a client uploads a second questionnaire in the same session, conflict review will compare those new answers against everything already answered in that session, not just the current file.

This works through LangGraph's checkpointer. The batch graph is compiled with a `MemorySaver` that persists state between invocations on the same session thread. At the end of each run, the system writes the merged completed results back into the checkpoint. At the start of the next run, it reads them back.

```text
First upload  (session_id = "abc")
  -> session memory loaded: empty
  -> 12 questions processed
  -> session memory saved: 12 completed answers

Second upload  (session_id = "abc")
  -> session memory loaded: 12 answers from first upload
  -> 8 new questions processed
  -> conflict review compares 8 new answers against all 20
  -> session memory saved: up to 20 answers
```

If no session ID is provided, the system generates a new one per request, making each upload independent.

---

## Clear Termination Logic

Every path through the workflow ends at a known terminal state. There are no open-ended loops.

### Per-Question

```text
retrieve historical evidence
  -> assess whether references are usable

     [not usable]
     -> return unanswered result

     [usable]
     -> generate answer
     -> validate answer

        [valid]
        -> return completed result

        [invalid, fewer than 3 attempts]
        -> retry generation with failure feedback

        [invalid, 3 attempts reached]
        -> return failed result
```

Every question exits with one of three statuses: `completed`, `unanswered`, or `failed`.

### Batch

```text
fan out one branch per question
  -> all branches run in parallel
  -> barrier: wait for all branches to finish
  -> run conflict review across all completed answers
  -> apply conflict findings to affected questions
  -> produce batch summary
  -> done
```

The barrier after question processing ensures conflict review only starts when all answers are available. The summary step always runs, even if every question failed, so the response is always well-formed.

---

## Short-Term State: What It Looks Like In Practice

Short-term state is the working memory inside one question's processing cycle.

Consider a question where the first generation attempt produces an empty answer. The workflow does not simply retry blindly. It records what went wrong, stores it in the question's state, and passes it directly to the next generation call as feedback.

The next generation attempt receives:

- the original question
- the same historical references
- the validation error from the previous attempt
- the failed answer text, if there was one

The model uses that context to correct its output. If the second attempt succeeds, the final response records that two attempts were needed. If it fails again and a third attempt is also needed, that is recorded too. After three failures, the question is marked as `failed` and processing stops.

This retry behaviour is entirely driven by what is in the question's state. Nothing outside that question is involved.

---

## Long-Term Memory: What It Looks Like In Practice

Long-term memory is the historical evidence stored in LanceDB. It persists to disk and survives server restarts.

### Writing Long-Term Memory

Historical content enters the system through the ingest endpoint:

```text
POST /api/ingest/history
files: [approved_tender_qa.csv, platform_overview.md]
```

A CSV file becomes structured question-answer records. Each record is embedded and stored in the `qa_records` table.

A Markdown file is split into paragraphs. Each paragraph is embedded and stored in the `document_records` table as a searchable evidence chunk.

Once ingested, that content is available to every future tender run. Ingesting the same file twice does not create duplicates.

### Reading Long-Term Memory

When a new tender question arrives, the retriever embeds it and searches both tables for the most semantically similar historical content.

For a question like:

> "Does your platform enforce TLS 1.2 or higher for all data in transit?"

The retriever might find:

- a previously approved Q/A record about TLS support from a prior tender
- a paragraph from a platform security overview document that describes encryption in transit

Those references are passed to the grounding assessor, which decides whether they are sufficient to support an answer. If they are, they become the evidence the answer is generated from.

Long-term memory is what allows the system to maintain historical positioning across clients even when question wording changes.

---

## The Three Layers Together

| Memory Layer | Timescale | What It Holds | How Long It Lasts |
|---|---|---|---|
| Short-term state | One question, one attempt | Retry feedback, validation errors, draft answers | Discarded when the question finishes |
| Session memory | One session, multiple uploads | Completed answers for conflict comparison | Lives in the server process for the session duration |
| Long-term memory | All sessions | Historical QA records and document evidence | Persists on disk across restarts |

Each layer does a job the others cannot.

Short-term state makes retry intelligent rather than repetitive. Session memory makes conflict review meaningful across uploads. Long-term memory makes the whole system historically grounded rather than generative from scratch.

---

## Related Documents

- Agent workflow design: [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md)
- Retrieval system design: [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md)
- Main project entry: [README.md](../../README.md)
