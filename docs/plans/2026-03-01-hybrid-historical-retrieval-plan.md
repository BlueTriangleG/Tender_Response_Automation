# Hybrid Historical Retrieval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend tender-answer grounding so retrieval uses both `qa_records` and `document_records`, merges the resulting evidence into one historical context set, and surfaces the mixed evidence cleanly in prompts and API responses.

**Architecture:** Keep retrieval split into two repositories with separate scoring and limits: QA retrieval remains high-precision question-answer evidence, while document retrieval contributes chunked supporting excerpts from non-tabular historical files. Add a hybrid evidence service that calls both, merges and caps results, and returns a unified `HistoricalAlignmentResult` for the existing LangGraph nodes. Prompt builders and public response schemas must then distinguish QA references from document-chunk references without breaking the existing workflow shape.

**Tech Stack:** FastAPI backend, LanceDB, LangGraph, LangChain chat-model prompting, existing OpenAI embeddings adapter, Pydantic, pytest

---

### Task 1: Lock the hybrid retrieval contract with failing tests

**Files:**
- Create: `backend/tests/features/tender_response/test_document_alignment_repository.py`
- Create: `backend/tests/features/tender_response/test_historical_evidence_service.py`
- Modify: `backend/tests/features/tender_response/test_qa_alignment_repository.py`
- Modify: `backend/tests/features/tender_response/test_reference_assessment_service.py`
- Modify: `backend/tests/features/tender_response/test_answer_generation_service.py`
- Create: `backend/tests/features/tender_response/test_mixed_reference_payloads.py`

**Step 1: Write failing tests for document chunk retrieval**

Create `test_document_alignment_repository.py` covering:
- returns no match when `document_records` is empty
- returns top chunk references when vectors are close
- preserves `source_doc`, `chunk_index`, excerpt text, and bounded score
- caps results at the configured top-k

**Step 2: Write failing tests for hybrid evidence merge**

Create `test_historical_evidence_service.py` covering:
- QA-only retrieval path
- document-only retrieval path
- mixed retrieval path with both source types
- merged ordering favors stronger scores while preserving both lanes
- combined result sets `matched=True` when either lane clears threshold

**Step 3: Extend existing QA repository tests to mixed-reference compatibility**

Update `test_qa_alignment_repository.py` so it still passes after the domain model gains reference type metadata.

**Step 4: Add failing tests for prompt/rendering updates**

Update:
- `test_reference_assessment_service.py`
- `test_answer_generation_service.py`
- `test_mixed_reference_payloads.py`

Cover:
- document chunks render as excerpts, not fake QA rows
- mixed evidence is accepted by assessment and generation prompts
- public API response exposes whether a reference came from QA or document chunk

**Step 5: Run the focused failing suite**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_qa_alignment_repository.py tests/features/tender_response/test_document_alignment_repository.py tests/features/tender_response/test_historical_evidence_service.py tests/features/tender_response/test_reference_assessment_service.py tests/features/tender_response/test_answer_generation_service.py tests/features/tender_response/test_mixed_reference_payloads.py -v
```

Expected:
- new hybrid/document tests fail
- current QA-only tests either still pass or fail only where new metadata is required

### Task 2: Generalize the historical reference domain model

**Files:**
- Modify: `backend/app/features/tender_response/domain/models.py`
- Modify: `backend/app/features/tender_response/schemas/responses.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/common/builders.py`
- Test: `backend/tests/features/tender_response/test_mixed_reference_payloads.py`

**Step 1: Extend `HistoricalReference`**

Add fields needed for mixed evidence:
- `reference_type: Literal["qa", "document_chunk"]`
- `excerpt: str | None = None`
- `chunk_index: int | None = None`

Keep existing fields for QA compatibility:
- `record_id`
- `question`
- `answer`
- `domain`
- `source_doc`
- `alignment_score`

Recommended rule:
- QA references keep `question` and `answer`
- document chunks use `excerpt` plus `chunk_index`, with `question=""` and `answer=""` or a similar explicit empty convention

**Step 2: Extend public `QuestionReference`**

Add:
- `reference_type`
- `excerpt: str | None = None`
- `chunk_index: int | None = None`

Keep existing QA-facing fields so the frontend contract evolves compatibly.

**Step 3: Update `build_reference_payload()`**

Render:
- QA references with matched question/answer
- document chunk references with excerpt/chunk metadata

**Step 4: Run schema and builder tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_mixed_reference_payloads.py tests/features/tender_response/test_response_schemas.py -v
```

Expected:
- mixed reference payloads validate cleanly

### Task 3: Add document chunk retrieval repository

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/repositories/document_alignment_repository.py`
- Modify: `backend/app/features/tender_response/infrastructure/repositories/__init__.py`
- Test: `backend/tests/features/tender_response/test_document_alignment_repository.py`

**Step 1: Implement document retrieval**

Create `DocumentAlignmentRepository` with:
- LanceDB connection
- embeddings client
- table target `settings.lancedb_document_table_name`

Core method:

```python
async def find_best_matches(
    self,
    question: TenderQuestion,
    *,
    threshold: float,
    limit: int = 4,
) -> list[HistoricalReference]:
    ...
```

**Step 2: Search and map rows**

For each `document_records` match:
- embed the incoming question once
- run `table.search(query_vector).limit(limit).to_list()`
- map `_distance` to `alignment_score = 1.0 / (1.0 + distance)`
- return only references at or above threshold when possible
- preserve near-misses if needed for downstream reasoning only if the tests require it

**Step 3: Map fields carefully**

Document chunk references should map:
- `record_id = id`
- `reference_type = "document_chunk"`
- `source_doc = source_doc`
- `excerpt = text`
- `chunk_index = chunk_index`
- `domain = domain`

**Step 4: Run repository tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_document_alignment_repository.py -v
```

Expected:
- document retrieval tests pass

### Task 4: Add a hybrid evidence service that merges QA and document lanes

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/services/historical_evidence_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/__init__.py`
- Test: `backend/tests/features/tender_response/test_historical_evidence_service.py`

**Step 1: Define lane policies explicitly**

Use separate caps:
- QA top-k = 3
- document top-k = 4
- combined cap = 5

Recommended merge rule:
- sort all candidates by `alignment_score` descending
- cap to 5 after merge
- if scores are effectively equal, prefer QA over document chunk

**Step 2: Implement hybrid retrieval**

Service constructor should accept:
- `qa_alignment_repository`
- `document_alignment_repository`

Main method:

```python
async def find_historical_evidence(
    self,
    question: TenderQuestion,
    *,
    threshold: float,
) -> HistoricalAlignmentResult:
    ...
```

**Step 3: Define `matched` semantics**

Set:
- `matched=True` if at least one merged reference clears threshold
- `record_id`, `question`, `answer`, `source_doc`, `alignment_score` from the top merged reference when it is a QA item
- for document-first matches, keep top-level fields conservative:
  - `record_id` from the top document chunk
  - `question=None`
  - `answer=None`
  - `source_doc` from the chunk
  - `alignment_score` from the chunk

This avoids pretending a document excerpt is a QA answer.

**Step 4: Run hybrid merge tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_historical_evidence_service.py -v
```

Expected:
- QA-only, document-only, and mixed retrieval cases pass

### Task 5: Replace QA-only retrieval in the workflow graph

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Modify: `backend/app/features/tender_response/application/tender_response_runner.py`
- Modify: any feature-local dependency wiring that instantiates retrieval services
- Test: `backend/tests/features/tender_response/test_process_tender_csv_use_case.py`
- Test: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Swap node dependency**

Change `make_retrieve_alignment_node()` to receive the hybrid evidence service instead of `QaAlignmentRepository`.

**Step 2: Preserve state shape**

Do not change `current_alignment` state shape beyond the richer reference objects. Keep downstream nodes intact where possible.

**Step 3: Update runner wiring**

Where the tender workflow is assembled, instantiate:
- `QaAlignmentRepository`
- `DocumentAlignmentRepository`
- `HistoricalEvidenceService`

Then inject the service into the retrieve node.

**Step 4: Run workflow assembly tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_process_tender_csv_use_case.py tests/features/tender_response/test_tender_response_graph.py -v
```

Expected:
- the graph still compiles and executes with the new retrieval service

### Task 6: Update reference assessment prompts for mixed evidence

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/prompting/reference_assessment.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py`
- Test: `backend/tests/features/tender_response/test_reference_assessment_service.py`

**Step 1: Render mixed reference payloads**

Change reference assessment payload generation to include:
- `reference_type`
- `source_doc`
- `alignment_score`
- for QA: `matched_question`, `matched_answer`
- for document chunks: `excerpt`, `chunk_index`

**Step 2: Keep assessment semantics strict**

Rules:
- QA rows can directly support a claim
- document chunks can support claims through excerpted evidence
- if only document chunks exist, `partial` should be common unless the excerpt is directly decisive
- conflicting evidence across source types still yields `none` / human review

**Step 3: Run assessment tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_reference_assessment_service.py -v
```

Expected:
- mixed evidence is classified correctly

### Task 7: Update grounded answer prompts for mixed evidence

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/prompting/answer_generation.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/answer_generation_service.py`
- Test: `backend/tests/features/tender_response/test_answer_generation_service.py`

**Step 1: Render reference lines by type**

For QA references:
- keep `question`, `answer`, `source_doc`

For document chunk references:
- render:
  - `Reference N type: document_chunk`
  - `Reference N excerpt: ...`
  - `Reference N chunk_index: ...`
  - `Reference N source_doc: ...`

**Step 2: Preserve partial-answer behavior**

Do not loosen the current grounded-answer guardrails. Document excerpts add support, but they should not encourage fabricated commitments.

**Step 3: Run generation tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_answer_generation_service.py -v
```

Expected:
- answer prompt tests pass with mixed evidence types

### Task 8: Extend integration coverage and data fixtures

**Files:**
- Modify: `backend/tests/integration/test_tender_response_route_integration.py`
- Optional: `test_data/historical_repository/*`
- Optional: `test_data/edge_case_suite/*`

**Step 1: Add one mixed-evidence route integration**

Create a route/integration case where:
- QA evidence alone is insufficient
- document chunk evidence adds supporting scope
- final response returns both reference types

**Step 2: Use stable fake embeddings**

Prefer deterministic in-memory LanceDB fixtures and fake embedding vectors so this test does not rely on live OpenAI.

**Step 3: Update sample fixtures only where necessary**

If the current `test_data/historical_repository/` files already cover the needed evidence, reuse them. Only add new files if a truly distinct mixed-evidence case is missing.

**Step 4: Run integration tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/integration/test_tender_response_route_integration.py -v
```

Expected:
- mixed evidence is returned through the public API

### Task 9: Full verification for the hybrid retrieval phase

**Files:**
- No new files

**Step 1: Run the focused tender-response suite**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_qa_alignment_repository.py tests/features/tender_response/test_document_alignment_repository.py tests/features/tender_response/test_historical_evidence_service.py tests/features/tender_response/test_reference_assessment_service.py tests/features/tender_response/test_answer_generation_service.py tests/features/tender_response/test_process_tender_csv_use_case.py tests/features/tender_response/test_tender_response_graph.py tests/features/tender_response/test_mixed_reference_payloads.py -v
```

Expected:
- all hybrid retrieval and prompt tests pass

**Step 2: Run the route/integration slice**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/integration/test_tender_response_route_integration.py tests/api/routes/test_tender_response_route.py -v
```

Expected:
- public route behavior still validates

**Step 3: Optional broader regression**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response -v
```

Expected:
- no regressions across the tender-response feature slice

### Assumptions

- This phase does **not** change the ingest pipeline; it only consumes the already-populated `document_records`.
- The frontend tender-response UI does not need immediate redesign beyond tolerating richer `references[]` payloads; the backend contract change is the priority.
- A document chunk can contribute evidence without being surfaced as a synthetic QA pair.
- QA evidence should still be preferred over document excerpts when both are equally relevant, because it is semantically closer to the tender-answer task.

### Suggested Commit Plan

1. `test: add failing coverage for hybrid historical retrieval`
2. `feat: add document chunk retrieval repository`
3. `feat: add hybrid evidence merge service`
4. `feat: support mixed evidence in tender workflow prompts`
5. `test: add mixed evidence route coverage`
