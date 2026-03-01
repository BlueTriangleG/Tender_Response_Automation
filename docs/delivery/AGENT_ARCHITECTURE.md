# Agent Architecture

This document describes the current multi-agent architecture used by the tender response workflow.

## Overview

The backend uses LangGraph to orchestrate a batch workflow over any number of tender questions. Each question runs in an isolated subgraph, while the batch graph aggregates results, preserves shared session memory, and performs session-level conflict review.

Core goals covered by this architecture:

- reference historical tender responses
- maintain consistency with historical positioning
- adapt answers to new wording and constraints
- isolate failures per question
- demonstrate state handling, short-term memory, and long-term memory

## Agent Responsibilities

### Retriever Agent

- Responsibility: find the most relevant historical references for a tender question
- Implementation:
  - `QaAlignmentRepository.find_best_match()`
  - `retrieve_alignment` node
- Inputs:
  - current question
  - alignment threshold
- Outputs:
  - top qualified historical references
  - alignment score and match metadata

### Grounding Assessor Agent

- Responsibility: decide whether retrieved evidence is sufficient
- Implementation:
  - `ReferenceAssessmentService.assess()`
  - `assess_references` node
  - `route_after_assessment()`
- Outputs:
  - `grounded`
  - `partial_reference`
  - `insufficient_reference`
  - `no_reference`

### Answer Composer Agent

- Responsibility: generate a grounded answer plus structured confidence and risk
- Implementation:
  - `AnswerGenerationService.generate_grounded_response()`
  - `generate_answer` node
- Inputs:
  - approved usable references
  - retry feedback from previous invalid attempts
  - assessment reason
- Outputs:
  - generated answer
  - confidence level and reason
  - risk level and reason
  - inconsistency signal

### Risk Guard Agent

- Responsibility: validate answer quality and enforce response policy
- Implementation:
  - `assess_output` node
  - `_validate_partial_answer_contract()`
  - `find_generation_validation_error()`
  - `fail_generation` node
- Responsibilities enforced:
  - partial answers must explain missing scope in parentheses
  - partial answers must reduce confidence appropriately
  - answers must not overstate unsupported claims
  - answers must not make absolute claims and then weaken themselves with exceptions
  - recoverable errors retry up to three times

### Conflict Reviewer Agent

- Responsibility: review completed answers for session-level contradictions
- Implementation:
  - `prepare_conflict_review`
  - `review_conflict_group`
  - `ConflictReviewService.review_conflicts()`
  - `apply_conflicts`
- Behavior:
  - reviews only `completed` answers with non-empty generated text
  - processes target questions in groups of up to 10
  - each group is checked against the full completed session answer set
  - results are validated server-side before being written back

## LangGraph Workflow

### Batch Graph

The outer graph handles:

- dispatching each tender question
- preserving shared session state
- invoking post-batch conflict review
- aggregating the final summary

High-level flow:

```text
START
  -> dispatch_questions
  -> process_question (fan-out)
  -> prepare_conflict_review
  -> review_conflict_group (parallel fan-out)
  -> apply_conflicts
  -> summarize_batch
  -> END
```

### Per-Question Subgraph

Each question runs independently:

```text
retrieve_alignment
  -> assess_references
  -> generate_answer or finalize_unanswered
  -> assess_output
  -> retry generate_answer up to 3 times if recoverable
  -> fail_generation or completed result
```

This design ensures one bad question does not stop the rest of the file.

## State Design

### Per-Question Short-Term State

`QuestionProcessingState` stores:

- current question
- retrieved references
- grounding assessment
- current answer draft
- confidence and risk review payload
- retry count
- validation error from previous attempts
- previous invalid answer and review metadata
- current terminal result

This is the short-term execution memory that lets the system correct itself instead of blindly retrying.

### Batch Shared State

`BatchTenderResponseState` stores:

- all question results for the current upload
- conflict findings
- conflict review errors
- batch summary
- `session_completed_results`

This is used for batch aggregation and session-wide consistency checks.

## Memory Model

### Short-Term Memory

Short-term memory is held in LangGraph state:

- retry memory inside `QuestionProcessingState`
- shared run state inside `BatchTenderResponseState`

This is how the system remembers:

- what failed validation
- which answer was previously invalid
- how many attempts have been used
- what prior completed answers already exist in the current session

### Long-Term Memory

Long-term memory is the LanceDB historical repository:

- previously approved Q/A rows
- document chunks from markdown, text, and JSON historical material

This is the persistent evidence base used to maintain historical positioning.

## Session Memory

The tender workflow uses `session_id` as the stable LangGraph thread key. If no `session_id` is supplied, it falls back to `request_id`.

Effect:

- multiple requests in the same session can reuse prior completed answers
- conflict review can compare current answers against earlier session answers
- this demonstrates shared session memory beyond a single file upload

## Safety Controls

- grounding gate before answer generation
- explicit `unanswered` path when evidence is insufficient
- bounded retry for recoverable validation failures
- per-question failure isolation
- conflict review after batch completion
- high-risk and inconsistent flags surfaced in the final response

## Why This Counts As Multi-Agent

The system is implemented as multiple specialized runtime agents with clear separation of concerns:

- retrieval
- grounding assessment
- answer composition
- output risk/quality control
- conflict review

Each agent owns a distinct decision boundary and exchanges structured state through LangGraph rather than opaque free-text handoff.
