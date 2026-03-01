# Tender Response Agent Responsibility Matrix

## Scope

This document is the production architecture record for agent responsibilities in the tender-response pipeline.
It defines runtime ownership, state contracts, memory boundaries, and safety controls for the LangGraph execution model.

## Agent Matrix

| Agent | Runtime Responsibility | Implementation Mapping | State Inputs | State Outputs |
| --- | --- | --- | --- | --- |
| Retriever Agent | Retrieve relevant historical QA evidence for each incoming tender question. | `make_retrieve_alignment_node()` + `QaAlignmentRepository.find_best_match()` | `current_question`, `alignment_threshold` | `current_alignment` |
| Grounding Assessor Agent | Evaluate evidence sufficiency and route execution to generation or fallback. | `make_assess_references_node()` + `route_after_assessment()` | `current_question`, `current_alignment` | `current_assessment`, route decision |
| Answer Composer Agent | Generate grounded answer content and structured confidence/risk rationale. | `make_generate_answer_node()` + `AnswerGenerationService.generate_grounded_response()` | `current_question`, usable references, retry feedback | `current_answer`, `current_review`, `generation_attempt_count` |
| Risk Guard Agent | Enforce output policy, validate response quality, manage retries, and materialize terminal states. | `make_assess_output_node()`, `_validate_partial_answer_contract()`, `make_fail_generation_node()`, `summarize_batch()` | `current_answer`, `current_review`, `current_assessment`, `current_alignment` | `current_result`, retry metadata, batch `summary` |

## Stage Responsibilities

### Retriever Agent

- **Runtime node:** `retrieve_alignment`
- **Responsibilities:**
  - Embed incoming question text in retrieval vector space.
  - Query LanceDB nearest-neighbor candidates.
  - Convert retrieval distance to normalized alignment score.
  - Return threshold-qualified references for downstream grounding.
- **Failure behavior:**
  - Produces structured miss state (`matched=False`) for empty tables and non-qualified matches.
  - Avoids exceptions for expected retrieval miss conditions.

### Grounding Assessor Agent

- **Runtime nodes:** `assess_references`, `route_after_assessment`
- **Responsibilities:**
  - Assess whether references are sufficient for safe answer generation.
  - Set grounding status (`grounded`, `partial_reference`, `insufficient_reference`, `no_reference`).
  - Route execution by grounding policy.
- **Failure behavior:**
  - Defaults to conservative fallback path when grounding criteria are not met.

### Answer Composer Agent

- **Runtime node:** `generate_answer`
- **Responsibilities:**
  - Generate answer using only approved references.
  - Return structured confidence and risk rationale.
  - Consume retry feedback from previous invalid outputs.
- **Failure behavior:**
  - Generation exceptions are isolated by the batch-level per-question guard.

### Risk Guard Agent

- **Runtime nodes:** `assess_output`, `fail_generation`, `summarize_batch`
- **Responsibilities:**
  - Validate output policy and response completeness.
  - Enforce partial-reference disclosure contract.
  - Detect high-risk and inconsistent responses.
  - Trigger bounded retries for recoverable validation failures.
  - Emit terminal failed result when retry policy is exhausted.
  - Aggregate batch summary and completion status.
- **Failure behavior:**
  - Contains failure at question scope; batch execution remains uninterrupted.

## State and Memory Boundaries

### Short-Term Execution State

- **Per-question state:** `QuestionProcessingState`
  - Holds transient retrieval, grounding, generation, and retry metadata.
- **Batch shared state:** `BatchTenderResponseState`
  - Holds aggregated question results, run errors, and final summary.

### Long-Term Memory

- **System memory source:** LanceDB QA table populated by history ingest.
- **Production role:** Preserve consistency with previously approved positioning through semantic retrieval.

## Orchestration and Safety Controls

- Outer graph dispatches isolated per-question flows and then aggregates outcomes.
- Per-question subgraph applies conditional routing:
  - grounding satisfied -> generate and validate answer;
  - grounding unsatisfied -> produce unanswered result.
- Safety controls are first-class runtime behavior via:
  - grounding gate before generation,
  - output contract validation and bounded retry policy,
  - explicit unanswered/failed terminal states,
  - batch-level failure isolation.


