# History Ingest Multi-Format Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend historical repository ingest so `.xlsx` uploads persist as QA records like `.csv`, and `.md` / `.json` / `.txt` uploads persist as document chunks in LanceDB, with tender retrieval combining both sources into answer context.

**Architecture:** Keep two storage lanes instead of forcing every file into the QA shape. Tabular files (`.csv`, `.xlsx`) normalize into `qa_records`; unstructured files (`.md`, `.json`, `.txt`) normalize into `document_records` as chunked evidence. Retrieval becomes hybrid: vector search QA references and document chunks separately, then merge both into a single evidence set for assessment and answer generation.

**Tech Stack:** FastAPI, Pydantic, LanceDB, LangGraph, existing OpenAI embeddings client, existing XML-based XLSX parsing pattern from tender-response feature

---

### Task 1: Lock the ingest contract and add failing tests for new file types

**Files:**
- Modify: `backend/tests/services/test_history_ingest_service.py`
- Modify: `backend/tests/file_processing/test_file_processing_service.py`
- Modify: `backend/tests/integration/test_csv_history_ingest_route.py`
- Create: `backend/tests/services/test_history_document_ingest_flow.py`

**Step 1: Write failing tests for `.xlsx` history ingest**

Add tests that upload `history.xlsx` and assert:
- the file is accepted
- the file persists rows into `qa_records`
- `storage_target == "qa_records"`
- column mapping still resolves `question`, `answer`, `domain`

**Step 2: Write failing tests for `.txt` parsing and document ingest**

Add tests that upload `.txt` and assert:
- the file parses successfully
- it no longer returns `unsupported_extension`
- it persists chunk rows into `document_records`
- `storage_target == "document_records"`

**Step 3: Write failing tests for `.md` / `.json` document ingest**

Add tests that upload `.md` and `.json` and assert:
- they are processed instead of failed with `unsupported_ingest_type`
- they persist chunk rows into `document_records`
- source metadata survives into stored rows

**Step 4: Add route-level mixed-batch test**

Add an integration test that uploads one `.csv`, one `.xlsx`, and one `.md`, then asserts:
- all three files are accepted
- QA rows land in `qa_records`
- document chunks land in `document_records`
- response counts are correct per file

**Step 5: Run the narrow failing test set**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py tests/file_processing/test_file_processing_service.py tests/integration/test_csv_history_ingest_route.py tests/services/test_history_document_ingest_flow.py -v
```

Expected:
- new `.xlsx` and document-ingest tests fail
- current `.csv` tests still pass

### Task 2: Add `.txt` and `.xlsx` parsing support to history ingest

**Files:**
- Modify: `backend/app/features/history_ingest/infrastructure/file_processing_service.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/text_parser.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/history_excel_parser.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/__init__.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/models.py`
- Test: `backend/tests/file_processing/test_file_processing_service.py`

**Step 1: Implement a plain text parser**

Create `text_parser.py` with:
- `extension = ".txt"`
- `parsed_kind = "text"`
- pass-through `raw_text`
- `structured_data = None`

**Step 2: Implement a history Excel parser**

Create `history_excel_parser.py` that:
- reads workbook bytes directly, not UTF-8 text
- reuses the XML/zip parsing approach already used in `tender_response/infrastructure/parsers/tender_excel_parser.py`
- extracts the first visible worksheet
- converts header row + data rows into `list[dict[str, str]]`
- returns a `ParsedFilePayload` with `parsed_kind = "spreadsheet"` and `extension = ".xlsx"`

**Step 3: Update file-processing orchestration**

Change `FileProcessingService` so:
- `.txt` and `.xlsx` are registered processors
- binary file parsers can receive raw bytes instead of always requiring UTF-8 decode first
- `.xlsx` malformed files return `parse_error`

**Step 4: Re-run parser tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py -v
```

Expected:
- `.txt` and `.xlsx` parsing tests pass

### Task 3: Split history ingest into QA lane and document lane

**Files:**
- Modify: `backend/app/features/history_ingest/application/ingest_history_use_case.py`
- Create: `backend/app/features/history_ingest/infrastructure/repositories/document_lancedb_repository.py`
- Create: `backend/app/features/history_ingest/infrastructure/services/document_chunking_service.py`
- Create: `backend/app/features/history_ingest/domain/document_chunk.py`
- Modify: `backend/app/features/history_ingest/schemas/responses.py`
- Test: `backend/tests/services/test_history_ingest_service.py`
- Test: `backend/tests/services/test_history_document_ingest_flow.py`

**Step 1: Add a document-chunk domain model**

Create a model that includes:
- `id`
- `document_id`
- `document_type`
- `domain`
- `title`
- `text`
- `source_doc`
- `chunk_index`
- `tags`
- `risk_topics`
- `client`
- `created_at`
- `updated_at`

**Step 2: Add a document chunking service**

Create `document_chunking_service.py` that:
- accepts one parsed non-tabular file
- derives a stable `document_id` from file name + content hash
- normalizes raw content into plain text
- chunks by size with overlap
- emits chunk records targeting `document_records`

Recommended defaults:
- chunk size: 800-1200 characters
- overlap: 100-150 characters

**Step 3: Add a document LanceDB repository**

Create `document_lancedb_repository.py` with:
- `upsert_records(records)`
- `get_existing_record_ids(record_ids)`
- table target `settings.lancedb_document_table_name`

**Step 4: Route files by ingest type**

Refactor `IngestHistoryUseCase.process_files()` so:
- `.csv` and `.xlsx` follow the existing QA normalization path
- `.md`, `.json`, `.txt` follow the new document chunk path
- response `storage_target` becomes `qa_records` or `document_records`
- non-supported types still fail cleanly

**Step 5: Keep `.json` unstructured in this phase**

Do not infer QA from arbitrary JSON. Instead:
- preserve JSON as text via deterministic serialization
- chunk serialized content into `document_records`

**Step 6: Run ingest service tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py tests/services/test_history_document_ingest_flow.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:
- mixed-format ingest passes
- `.md` / `.json` / `.txt` no longer fail with `unsupported_ingest_type`

### Task 4: Add document retrieval and hybrid evidence aggregation

**Files:**
- Modify: `backend/app/features/tender_response/domain/models.py`
- Modify: `backend/app/features/tender_response/infrastructure/repositories/qa_alignment_repository.py`
- Create: `backend/app/features/tender_response/infrastructure/repositories/document_alignment_repository.py`
- Create: `backend/app/features/tender_response/infrastructure/services/historical_evidence_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Create: `backend/tests/features/tender_response/test_document_alignment_repository.py`
- Modify: `backend/tests/features/tender_response/test_qa_alignment_repository.py`
- Create: `backend/tests/features/tender_response/test_historical_evidence_service.py`

**Step 1: Generalize the evidence model**

Extend `HistoricalReference` or introduce a sibling model so retrieval payload can represent:
- `reference_type` = `qa` or `document_chunk`
- optional `question`
- answer or excerpt text
- source file
- alignment score
- chunk index for document chunks

**Step 2: Add document chunk retrieval**

Implement `document_alignment_repository.py` that:
- embeds the incoming tender question
- searches `document_records`
- returns top `N` chunk references with bounded score calculation matching QA retrieval

**Step 3: Add a hybrid evidence service**

Create `historical_evidence_service.py` that:
- calls QA retrieval and document retrieval
- applies independent top-k and threshold rules
- merges, sorts, and caps the combined evidence list
- preserves source type for prompt rendering and response payload

**Step 4: Replace direct QA-only retrieval in workflow**

Update `make_retrieve_alignment_node()` so it uses the hybrid evidence service instead of calling `QaAlignmentRepository.find_best_match()` directly.

**Step 5: Define merge rules explicitly**

Recommended merge policy:
- QA top-k = 3
- document top-k = 4
- combined cap = 5
- always prefer QA items first when scores are close because they are higher-precision historical answers

**Step 6: Run hybrid retrieval tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_qa_alignment_repository.py tests/features/tender_response/test_document_alignment_repository.py tests/features/tender_response/test_historical_evidence_service.py -v
```

Expected:
- questions can retrieve QA-only, document-only, or mixed evidence

### Task 5: Update reference assessment and answer prompts to understand mixed evidence

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/prompting/reference_assessment.py`
- Modify: `backend/app/features/tender_response/infrastructure/prompting/answer_generation.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/common/builders.py`
- Modify: `backend/app/features/tender_response/schemas/responses.py`
- Test: `backend/tests/features/tender_response/test_reference_assessment_service.py`
- Test: `backend/tests/features/tender_response/test_answer_generation_service.py`
- Create: `backend/tests/features/tender_response/test_mixed_reference_payloads.py`

**Step 1: Update prompt rendering**

Render mixed evidence with explicit labels, for example:
- `Reference 1 type: qa`
- `Reference 2 type: document_chunk`
- for QA: include matched question + answer
- for document chunks: include excerpt text + chunk index + source file

**Step 2: Update assessment rules**

Teach reference assessment that:
- document chunks can supply supporting evidence
- QA rows remain stronger direct-answer evidence
- partial grounding is expected when only document chunks exist

**Step 3: Extend API response payload if needed**

Update `QuestionReference` so the frontend can tell whether a reference came from:
- `qa`
- `document_chunk`

Also include optional `excerpt` or `chunk_index` when the source is a document chunk.

**Step 4: Add mixed-evidence tests**

Cover:
- QA-only grounding
- document-only partial grounding
- combined QA + document grounding
- response payload includes source type

**Step 5: Run prompt/service tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_reference_assessment_service.py tests/features/tender_response/test_answer_generation_service.py tests/features/tender_response/test_mixed_reference_payloads.py -v
```

Expected:
- prompts and schema validations pass with mixed evidence

### Task 6: End-to-end verification and cleanup

**Files:**
- Modify: `README.md`
- Optional: `test_data/historical_repository/*`
- Optional: `test_data/edge_case_suite/historical_repository/*`

**Step 1: Add representative fixture files**

Add or reuse fixtures for:
- `.csv`
- `.xlsx`
- `.md`
- `.json`
- `.txt`

**Step 2: Add one integration scenario for hybrid retrieval**

Write an integration test where:
- a tender question retrieves both a QA record and a document chunk
- the final response returns both references

**Step 3: Update README**

Document the new supported history-ingest matrix:
- `.csv` and `.xlsx` -> `qa_records`
- `.md`, `.json`, `.txt` -> `document_records`

**Step 4: Run the full targeted backend suite**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py tests/file_processing/test_file_processing_service.py tests/integration/test_csv_history_ingest_route.py tests/features/tender_response/test_qa_alignment_repository.py tests/features/tender_response/test_reference_assessment_service.py tests/features/tender_response/test_answer_generation_service.py tests/features/tender_response/test_tender_response_modules.py -v
```

Expected:
- all history-ingest and tender-response tests pass

**Step 5: Run the broader backend suite**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests -v
```

Expected:
- no regressions outside ingest and tender-response

### Design Notes

- Do not literally concatenate every non-tabular file into one global mega-document. Store one logical document per source file, then chunk it. This preserves provenance, dedupe, targeted re-ingest, and debugging.
- Do not force arbitrary `.json` into QA normalization. JSON should be treated as evidence text unless you later introduce a strict JSON QA schema.
- Keep QA retrieval and document retrieval separate internally, even if they merge before prompt generation. This keeps scoring and later tuning manageable.
- Prefer reusing the existing XML-based `.xlsx` parsing pattern already present in the tender-response feature instead of adding a heavy spreadsheet dependency just for history ingest.

### Suggested Commit Plan

1. `test: add failing coverage for xlsx and document history ingest`
2. `feat: add txt and xlsx parsing for history ingest`
3. `feat: persist non-tabular history files as document chunks`
4. `feat: add hybrid qa and document retrieval`
5. `feat: support mixed historical references in answer generation`
6. `docs: document multi-format history ingest`
