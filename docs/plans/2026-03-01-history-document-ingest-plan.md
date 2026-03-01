# History Document Ingest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `.txt`, `.md`, and `.json` history ingest support that stores chunked document evidence in LanceDB `document_records`, and wire the frontend repository upload flow to support and surface that document-ingest path clearly.

**Architecture:** Keep history ingest split into two lanes. Tabular uploads (`.csv`, `.xlsx`) continue to normalize into `qa_records`; unstructured uploads (`.txt`, `.md`, `.json`) are parsed as raw evidence text, chunked deterministically per source file, embedded, and written into `document_records`. The frontend repository tab remains a single batch uploader, but its accepted types, queue messaging, and result display must clearly reflect document ingestion outcomes.

**Tech Stack:** FastAPI, Pydantic, LanceDB, existing OpenAI embeddings client, React, Vitest

---

### Task 1: Lock the non-tabular ingest contract with failing tests

**Files:**
- Modify: `backend/tests/services/test_history_ingest_service.py`
- Create: `backend/tests/services/test_history_document_ingest_flow.py`
- Modify: `backend/tests/file_processing/test_file_processing_service.py`
- Modify: `backend/tests/integration/test_csv_history_ingest_route.py`
- Modify: `frontend/src/App.test.tsx`

**Step 1: Write failing parser test for `.txt`**

Add a test to `backend/tests/file_processing/test_file_processing_service.py` that uploads `history.txt` and asserts:
- `status == "processed"`
- `payload.parsed_kind == "text"`
- `payload.raw_text` is preserved
- `payload.structured_data is None`

**Step 2: Write failing service tests for `.md`, `.json`, `.txt` document ingest**

Create `backend/tests/services/test_history_document_ingest_flow.py` covering:
- `.md` persists document chunks into `document_records`
- `.json` persists document chunks into `document_records`
- `.txt` persists document chunks into `document_records`
- each processed file returns `storage_target == "document_records"`
- `processed_file_count` increments instead of returning `unsupported_ingest_type`

**Step 3: Write failing route-level mixed-batch test**

Extend `backend/tests/integration/test_csv_history_ingest_route.py` with one request that uploads:
- one `.csv`
- one `.xlsx`
- one `.md`
- one `.txt`

Assert:
- route returns `200`
- tabular files land in `qa_records`
- non-tabular files land in `document_records`
- response shows mixed `storage_target` values

**Step 4: Write failing frontend test for `.txt` repository upload**

Extend `frontend/src/App.test.tsx` so the repository uploader accepts a `.txt` file into the queue and shows the updated support text.

**Step 5: Run only the new failing tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py tests/services/test_history_document_ingest_flow.py tests/integration/test_csv_history_ingest_route.py -k "txt or document or mixed_batch" -v
```

Run:
```bash
cd frontend
npm test -- src/App.test.tsx
```

Expected:
- new non-tabular ingest tests fail
- existing CSV/XLSX ingest tests still pass

### Task 2: Add parser support for `.txt` and normalize non-tabular parser outputs

**Files:**
- Modify: `backend/app/features/history_ingest/infrastructure/file_processing_service.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/text_parser.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/__init__.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/models.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/json_parser.py`
- Modify: `backend/app/features/history_ingest/infrastructure/parsers/markdown_parser.py`
- Test: `backend/tests/file_processing/test_file_processing_service.py`

**Step 1: Add a text parser**

Create `text_parser.py`:

```python
class TextParser:
    extension = ".txt"
    parsed_kind = "text"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        raw_text = content.raw_text or ""
        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=raw_text,
            structured_data=None,
            row_count=None,
            warnings=[],
        )
```

**Step 2: Register `.txt` in `FileProcessingService`**

Update the processor list so history ingest accepts:
- `.csv`
- `.xlsx`
- `.json`
- `.md`
- `.txt`

**Step 3: Keep parser inputs consistent**

Preserve:
- `raw_bytes` for binary inputs
- `raw_text` for text inputs

No schema changes beyond what is required for parser interoperability.

**Step 4: Run parser tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py -v
```

Expected:
- `.txt` parser test passes
- existing `.json`, `.md`, `.csv`, `.xlsx` parser tests stay green

### Task 3: Add document chunk domain model and LanceDB repository

**Files:**
- Create: `backend/app/features/history_ingest/domain/document_chunk.py`
- Create: `backend/app/features/history_ingest/infrastructure/repositories/document_lancedb_repository.py`
- Modify: `backend/app/features/history_ingest/infrastructure/repositories/__init__.py`
- Test: `backend/tests/services/test_history_document_ingest_flow.py`

**Step 1: Add a `DocumentChunkRecord` model**

Create a small domain model with:
- `id`
- `document_id`
- `document_type`
- `domain`
- `title`
- `text`
- `source_doc`
- `tags`
- `risk_topics`
- `client`
- `chunk_index`
- `created_at`
- `updated_at`

**Step 2: Add a LanceDB repository for document chunks**

Create `document_lancedb_repository.py` with:
- `upsert_records(records: list[dict[str, Any]]) -> None`
- `get_existing_record_ids(record_ids: list[str]) -> set[str]`

Target table:
- `settings.lancedb_document_table_name`

Implementation should mirror the QA repository pattern:

```python
table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(records)
```

**Step 3: Add repository export**

Expose the repository from `infrastructure/repositories/__init__.py` for feature-local imports.

**Step 4: Run repository-backed failing tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_document_ingest_flow.py -v
```

Expected:
- failures move from “missing repository” to “missing chunking/orchestration”

### Task 4: Add deterministic document chunking service

**Files:**
- Create: `backend/app/features/history_ingest/infrastructure/services/document_chunking_service.py`
- Modify: `backend/app/features/history_ingest/infrastructure/services/__init__.py`
- Test: `backend/tests/services/test_history_document_ingest_flow.py`

**Step 1: Define chunking rules**

Implement a simple deterministic chunker with:
- chunk size: 1000 characters
- overlap: 150 characters
- whitespace normalization

**Step 2: Define document identity**

Generate:
- `document_id = sha256(file_name + "\n" + normalized_text)`
- `chunk_id = sha256(document_id + f":{chunk_index}")`

This gives stable dedupe across re-ingest of identical content.

**Step 3: Serialize source text per file type**

Rules:
- `.md`: use raw markdown text
- `.txt`: use raw plain text
- `.json`: use deterministic pretty JSON text, for example `json.dumps(parsed_json, ensure_ascii=True, sort_keys=True, indent=2)`

**Step 4: Build chunk payloads**

Each chunk record should include:
- `document_type` based on extension or parsed kind
- `title` defaulting to file name
- `source_doc` = original file name
- `chunk_index`
- `text`

Keep `domain`, `tags`, `risk_topics`, and `client` null or empty in this phase unless you can derive them cheaply without heuristics.

**Step 5: Run chunking tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_document_ingest_flow.py -v
```

Expected:
- chunking tests pass
- duplicate re-ingest tests can now assert zero new rows

### Task 5: Split `IngestHistoryUseCase` into QA lane and document lane

**Files:**
- Modify: `backend/app/features/history_ingest/application/ingest_history_use_case.py`
- Modify: `backend/app/features/history_ingest/api/dependencies.py`
- Modify: `backend/app/features/history_ingest/schemas/responses.py`
- Test: `backend/tests/services/test_history_ingest_service.py`
- Test: `backend/tests/services/test_history_document_ingest_flow.py`
- Test: `backend/tests/integration/test_csv_history_ingest_route.py`

**Step 1: Inject document services**

Update the use case constructor to accept:
- `document_chunking_service`
- `document_repository`

**Step 2: Route by file extension**

Keep this decision tree:
- `.csv`, `.xlsx` -> existing QA ingest path
- `.md`, `.json`, `.txt` -> new document ingest path
- anything else -> `unsupported_extension`

**Step 3: Add a document-ingest helper**

Extract the non-tabular branch into a helper method:

```python
async def _process_document_file(self, parsed_payload: ParsedFilePayload) -> ProcessedHistoryFileResult:
    ...
```

That helper should:
- chunk the parsed file
- dedupe by chunk id using `document_repository.get_existing_record_ids(...)`
- embed chunk texts using the existing `QaEmbeddingService`
- upsert chunk rows into `document_records`
- return `ProcessedHistoryFileResult(..., storage_target="document_records")`

**Step 4: Keep API response shape stable**

Do not add a new endpoint. Preserve `POST /api/ingest/history` and the current response model; only behavior changes.

**Step 5: Run service + integration tests**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py tests/services/test_history_document_ingest_flow.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:
- `.md`, `.json`, `.txt` are processed
- `.csv`, `.xlsx` remain QA-backed
- mixed batches pass end-to-end

### Task 6: Wire the frontend repository flow to non-tabular document ingest

**Files:**
- Modify: `frontend/src/components/BatchUploadDropzone.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/lib/api.test.ts`
- Optional: `frontend/src/lib/types.ts`

**Step 1: Expand accepted file types**

Update the repository dropzone to support:
- `.json`
- `.md`
- `.txt`
- `.csv`
- `.xlsx`

UI text should say exactly that.

**Step 2: Keep queue logic generic**

Do not add separate frontend queues for QA and document files in this phase. One batch queue is enough.

**Step 3: Improve repository result messaging**

In `frontend/src/App.tsx`, when rendering latest ingest results:
- show `Target: qa_records` or `Target: document_records`
- optionally add a small derived label such as `QA table` or `Document chunks`
- preserve existing failure rendering

**Step 4: Add frontend tests**

Cover:
- `.txt` appears in the repository queue
- mixed queue (`.json`, `.md`, `.txt`, `.csv`, `.xlsx`) is accepted
- ingest result rendering shows both `qa_records` and `document_records`

**Step 5: Run frontend tests**

Run:
```bash
cd frontend
npm test -- src/App.test.tsx src/lib/api.test.ts
```

Expected:
- repository uploader accepts all supported history file types
- mixed ingest results render cleanly

### Task 7: Add test data and docs for the new document-ingest path

**Files:**
- Create: `test_data/historical_repository/operations_playbook.txt`
- Modify: `test_data/README.md`
- Modify: `README.md`

**Step 1: Add a representative `.txt` sample**

Create `test_data/historical_repository/operations_playbook.txt` with 2-4 paragraphs of realistic platform operations language so manual ingest testing has a plain-text source.

**Step 2: Update dataset docs**

Document that `historical_repository/` now contains:
- tabular QA files for `qa_records`
- non-tabular evidence files for `document_records`

**Step 3: Update top-level README**

Change the history ingest description from CSV/XLSX-only to:
- tabular QA ingest for `.csv` / `.xlsx`
- document evidence ingest for `.md` / `.json` / `.txt`

**Step 4: Manual smoke guidance**

Document a manual validation flow:
1. Upload one `.csv`
2. Upload one `.md`
3. Upload one `.txt`
4. Confirm latest ingest results show both storage targets

### Task 8: Full verification for this phase

**Files:**
- No new files

**Step 1: Run the backend test slice**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py tests/services/test_history_ingest_service.py tests/services/test_history_document_ingest_flow.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:
- all history-ingest tests pass

**Step 2: Run the frontend test slice**

Run:
```bash
cd frontend
npm test -- src/App.test.tsx src/lib/api.test.ts
```

Expected:
- all repository upload and render tests pass

**Step 3: Optional broader regression**

Run:
```bash
cd backend
../backend/.venv/bin/pytest tests/services/test_history_ingest_csv_flow.py -v
```

Expected:
- CSV/XLSX QA ingest still passes after introducing document ingest

### Assumptions

- This phase does **not** implement document retrieval inside tender answering. It only persists document evidence and exposes it cleanly through the existing ingest workflow.
- Arbitrary `.json` files are treated as evidence text, not schema-aware QA rows.
- One repository batch uploader remains sufficient for the current frontend UX.
- The same embedding model used for QA rows is acceptable for document chunk embeddings in this phase.

### Suggested Commit Plan

1. `test: add failing coverage for document history ingest`
2. `feat: add txt parser and document chunking`
3. `feat: persist non-tabular history files to document records`
4. `feat: update repository upload flow for document ingest`
5. `docs: document history document ingest support`
