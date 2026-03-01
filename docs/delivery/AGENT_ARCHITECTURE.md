# Agent Architecture

This document explains the current tender response design in plain language.

You do not need to know LangGraph to read it. The point is to make the system shape obvious:

- what the workflow is trying to do
- how work moves through the graph
- where parallelism happens
- how state and memory are used
- why the system is split into several runtime roles instead of one large prompt

For the retrieval-specific design, see [RAG_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/RAG_ARCHITECTURE.md).

## Design Goal

The service receives a tender questionnaire, looks up historical evidence, generates one response per question, and returns a structured batch result.

The core design requirements are simple:

- each question should be processed independently so one failure does not block the batch
- answers must stay aligned with historical positioning
- the workflow must keep short-term state during the run and shared memory across a session
- the system must review the final batch for conflicts between answers

That is why the workflow is modeled as a graph instead of a single request-response model call.

## Workflow First

The easiest way to understand the system is to start with the flow rather than the code.

There are two layers:

1. a batch graph for the uploaded file
2. a per-question subgraph for each tender question

The batch graph owns the whole file.
The per-question graph owns one question at a time.

## Batch Graph

The outer graph is responsible for the uploaded questionnaire as a whole.

High-level flow:

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

What each stage means:

- `dispatch_questions`
  - turns the questionnaire into one unit of work per question
- `process_question`
  - runs the full per-question subgraph
  - each question is isolated from the others
- `prepare_conflict_review`
  - waits until all questions finish
  - collects completed answers and session memory
- `review_conflict_group`
  - checks whether answers contradict each other
  - runs in parallel over groups of target questions
- `apply_conflicts`
  - validates and writes conflict findings back to the affected questions
- `summarize_batch`
  - produces the final counts and overall completion status

In practice, this outer graph is what gives the system its batch behavior:

- dynamic handling of any file size in the expected range
- clear batch completion logic
- shared session memory
- post-run consistency checking

## Per-Question Graph

Each question gets its own isolated workflow.

High-level flow:

```text
retrieve_alignment
  -> assess_references
  -> generate_answer or finalize_unanswered
  -> assess_output
  -> retry generate_answer up to 3 times if recoverable
  -> fail_generation or completed result
```

In plain language:

- first find the best historical evidence
- then decide whether that evidence is good enough
- if not good enough, return `unanswered`
- if good enough, generate an answer
- validate whether that answer is safe and contract-compliant
- if the answer is fixable, retry with feedback
- if retries are exhausted, mark only that question as `failed`

This is the key reason one broken answer does not break the whole run.

## Where Parallelism Happens

Parallelism is a design choice here, not an afterthought.

### Parallelism Level 1: Question Processing

After upload parsing, the batch graph fans out one `process_question` task per tender question.

Effect:

- question `q-001` does not wait for `q-002`
- slow or failed questions do not block already-finished questions
- the system scales naturally with the number of questions in the file

This is the main throughput gain in the system.

### Parallelism Level 2: Conflict Review

After question processing finishes, the system performs session-level conflict review.

It does not compare answers one by one in sequence. Instead:

- it selects completed answers only
- it groups target questions in batches of up to 10
- it runs multiple conflict review jobs in parallel
- each job checks its target questions against the full completed answer set for the session

This keeps the review fast without narrowing it to only local pairs.

## Why A Graph Is Better Than A Single Prompt

One large prompt could try to do everything, but it would blur responsibilities:

- retrieval
- grounding judgment
- answer generation
- validation
- retry
- batch conflict review

The graph keeps those concerns separate.

Benefits:

- each stage has a clear purpose
- failure handling is explicit
- retry is controlled by state, not hidden inside one long prompt
- session memory can be reused across multiple requests
- post-batch consistency review becomes possible
- the backend is easier to test, lint, and type-check because the workflow contracts are explicit

In short, the graph turns the system from “one model trying to do everything” into a workflow with explicit control points.

## Agent Design

The word “agent” here means a runtime role with a narrow responsibility.

Each agent owns a specific decision boundary and reads or writes a specific part of state.

## Agent Responsibilities

### Retriever Agent

Purpose:

- find the best historical evidence for the current question

Why it exists:

- retrieval should be separate from generation
- the workflow should answer from stored evidence, not from model intuition

Implementation mapping:

- `QaAlignmentRepository.find_best_match()`
- `retrieve_alignment`

Output:

- qualified historical references
- alignment metadata

The retriever uses a hybrid RAG design over `qa_records` and `document_records`, described in [RAG_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/RAG_ARCHITECTURE.md).

### Grounding Assessor Agent

Purpose:

- decide whether the retrieved evidence is enough for a safe answer

Why it exists:

- relevance is not the same thing as answerability
- some questions are fully supported
- some are only partially supported
- some should not be answered at all

Implementation mapping:

- `ReferenceAssessmentService.assess()`
- `assess_references`
- `route_after_assessment()`

Possible decisions:

- `grounded`
- `partial_reference`
- `insufficient_reference`
- `no_reference`

### Answer Composer Agent

Purpose:

- generate answer text plus structured confidence and risk metadata

Why it exists:

- answer writing is a different job from evidence qualification
- the system needs both human-readable prose and machine-readable review signals

Implementation mapping:

- `AnswerGenerationService.generate_grounded_response()`
- `generate_answer`

Inputs:

- current question
- usable references only
- retry feedback from previous invalid attempts
- assessment reason

Outputs:

- generated answer
- confidence level and reason
- risk level and reason
- inconsistency signal

### Risk Guard Agent

Purpose:

- validate the generated answer before it is accepted

Why it exists:

- generation alone is not enough
- the workflow must block overclaims, malformed partial answers, and inconsistent wording

Implementation mapping:

- `assess_output`
- `_validate_partial_answer_contract()`
- `find_generation_validation_error()`
- `fail_generation`

What it enforces:

- partial answers must disclose missing scope in parentheses
- partial answers must reduce confidence appropriately
- unsupported claims must not pass through
- absolute claims must not be weakened by later caveats
- recoverable issues retry up to three times

### Conflict Reviewer Agent

Purpose:

- check whether completed answers contradict each other across the session

Why it exists:

- answers can look fine in isolation and still conflict at batch level

Implementation mapping:

- `prepare_conflict_review`
- `review_conflict_group`
- `ConflictReviewService.review_conflicts()`
- `apply_conflicts`

Behavior:

- reviews only completed answers with displayable answer text
- checks current batch plus prior completed session answers
- runs in parallel over grouped targets
- validates findings before writing them back

## State Design

LangGraph works by passing explicit state through the graph.

In this project, there are two state scopes.

### Per-Question State

`QuestionProcessingState` is the short-term working memory for one question.

It stores:

- the current question
- retrieved references
- grounding assessment
- answer draft
- confidence and risk review payload
- retry count
- last validation error
- previous invalid answer details
- final question result

This is what allows retry to behave like correction rather than blind repetition.

### Batch State

`BatchTenderResponseState` is the shared state for the uploaded file.

It stores:

- all question results for the current upload
- conflict findings
- conflict review errors
- summary metrics
- `session_completed_results`

This is what lets the system move from isolated question processing to whole-batch reasoning.

## Memory Design

### Short-Term Memory

Short-term memory is state that exists during workflow execution.

Examples in this system:

- the last invalid answer for a question
- the validation error that triggered retry
- the retry count
- completed answers already produced in the current session

This memory is operational. It helps the workflow make the next decision correctly.

### Long-Term Memory

Long-term memory is the historical evidence base in LanceDB.

It contains:

- previously approved Q/A records
- historical document chunks from markdown, text, and JSON inputs

This memory is referential. It provides the evidence used to maintain historical positioning.

### Shared Session Memory

The workflow uses `session_id` as the stable thread key. If no `session_id` is provided, it falls back to `request_id`.

Design effect:

- repeated requests in the same session can reuse prior completed answers
- conflict review can compare new answers with earlier session outputs
- the system can demonstrate memory beyond a single upload

## Safety And Failure Model

The system is designed to fail conservatively.

Safety controls include:

- grounding gate before generation
- explicit `unanswered` path when evidence is insufficient
- bounded retry for recoverable generation problems
- per-question failure isolation
- post-batch conflict review
- high-risk and inconsistency flags in the final response

In practice, that means the system prefers:

- partial but honest answers
- unanswered results when evidence is too weak
- failed single-question outputs over unsafe overclaiming

## Why This Qualifies As Multi-Agent

This design is multi-agent because the workflow is intentionally split into specialized decision-makers, each with:

- a distinct responsibility
- explicit state inputs
- explicit state outputs
- a clear place in the graph

The important point is not the number of model calls. The important point is that retrieval, grounding, composition, validation, and conflict review are separate runtime roles with explicit handoff between them.

That separation of concerns is the core design principle behind this architecture.
