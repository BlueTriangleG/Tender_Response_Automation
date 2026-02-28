# History Ingest API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a backend ingest API that accepts one or many uploaded history files from the frontend, restores and reads `json`, `md`, and `csv` files on the server, and routes them through a reusable file-processing module. This phase stops before LanceDB persistence, table mapping, or business-specific extraction logic.

**Architecture:** Use a single FastAPI ingest endpoint for batch multipart uploads. The route accepts `UploadFile` items under one `files` field, delegates them to a reusable processing layer that normalizes metadata, validates supported types, reads content safely, and emits a common parsed payload shape, then returns both per-file results and batch-level summary data. Keep LanceDB as a downstream boundary only: this API proves transport and parsing, not storage.

**Tech Stack:** FastAPI, Starlette `UploadFile`, Pydantic, Python stdlib `json` and `csv`, markdown text reader, pytest, `TestClient`.

---

## Scope

Included:

- frontend-to-backend file transport contract
- backend batch ingest endpoint
- server-side restoration and reading of uploaded files
- reusable file processor module for `json`, `md`, and `csv`
- normalized parsed output contract
- batch response summarizing all parsed files
- service boundary for future LanceDB handoff

Excluded:

- deciding which LanceDB table a file should populate
- business-specific field extraction rules
- embedding generation
- chunking strategy
- retrieval logic
- frontend implementation

## Recommended Design

### Option 1: Batch multipart ingest + processor registry

This is the recommended path.

- use `multipart/form-data`
- accept one or many files in the same request
- use `UploadFile` to avoid loading the whole body into the request model layer
- dispatch each file to a processor selected by normalized extension/content type
- emit one common result shape for all processors
- return both per-file results and a batch summary

Why this is the right default:

- native FastAPI path for browser uploads
- easy for frontend forms and `FormData`
- keeps transport concerns separate from parsing concerns
- easy to extend to future file types
- matches your “upload many files and parse them in one shot” requirement

### Option 2: Base64 file contents inside JSON

Do not choose this.

- larger payloads
- worse developer ergonomics
- unnecessary manual encoding/decoding in frontend and backend

### Option 3: One endpoint per file type

Do not choose this in v1.

- duplicates validation and transport logic
- makes mixed-file upload harder
- overfits before business rules exist

## API Contract

Use one endpoint:

- route path: `POST /ingest/history`
- effective URL in the current backend structure: `POST /api/ingest/history`

Request:

- content type: `multipart/form-data`
- field name: `files`
- supports one or many files
- optional metadata fields may be added later, but not required in v1

Response shape:

- ingest request id
- total file count
- processed file count
- failed file count
- per-file status
- normalized file metadata
- parsed content summary
- extracted raw content payload in a common shape
- processing errors per file without aborting the entire batch

Recommended response semantics:

- return `200` when the request is syntactically valid, even if some files fail processing
- mark each file independently as `processed` or `failed`
- return `422` only for invalid request structure such as missing files

## Processing Boundary

The processing layer should answer only these questions:

- what file was uploaded
- is this file type supported
- how do we read it safely
- what normalized content can we extract right now

The processing layer should not answer:

- which DB table to use
- how to chunk or embed the content
- which business entity a row belongs to

## Reusable File Module

Use a processor registry with one processor per file type.

Recommended modules:

- `app/file_processing/models.py`
- `app/file_processing/base.py`
- `app/file_processing/processors/json_processor.py`
- `app/file_processing/processors/markdown_processor.py`
- `app/file_processing/processors/csv_processor.py`
- `app/file_processing/service.py`
- `app/services/history_ingest_service.py`

Recommended common output model:

- `file_name`
- `extension`
- `content_type`
- `size_bytes`
- `parsed_kind`
- `raw_text`
- `structured_data`
- `row_count`
- `warnings`

Processor behavior:

- `json`: decode UTF-8, parse JSON, preserve structured object, also produce normalized text form
- `md`: decode UTF-8, preserve raw markdown text
- `csv`: decode UTF-8, parse rows and headers, preserve structured row list and normalized text form

## Batch Ingest Behavior

One request should be able to parse many files in one shot.

Recommended behavior:

- loop through all uploaded files in request order
- process each file independently
- continue if one file fails
- accumulate a final batch summary
- return all per-file results in one response

This keeps the server dynamically updateable because parsed output is immediately available in memory after the request finishes, even though this phase does not write to LanceDB yet.

## Error Handling

Handle errors per file, not per batch.

Expected cases:

- unsupported extension
- invalid JSON syntax
- invalid CSV decode or malformed rows
- empty file
- unreadable stream

Recommended behavior:

- continue processing other files
- include a stable error code and message in the per-file result
- read each `UploadFile` exactly once in the processor service

## Implementation Tasks

### Task 1: Add schemas for ingest responses and parsed results

**Files:**
- Create: `backend/app/schemas/history_ingest.py`
- Create: `backend/tests/schemas/test_history_ingest_schema.py`

**Step 1: Write the failing tests**

Cover:

- parsed result model supports common metadata fields
- file result model supports success and failure states
- batch response model supports multiple file results
- batch response model supports summary counters

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_schema.py -v
```

Expected:

- FAIL because the schema module does not exist yet

**Step 3: Write minimal implementation**

Add models such as:

- `ParsedFilePayload`
- `ProcessedHistoryFileResult`
- `HistoryIngestResponse`

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_schema.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/schemas/history_ingest.py backend/tests/schemas/test_history_ingest_schema.py
git commit -m "feat: add history ingest schemas"
```

### Task 2: Build the reusable file processing module

**Files:**
- Create: `backend/app/file_processing/__init__.py`
- Create: `backend/app/file_processing/models.py`
- Create: `backend/app/file_processing/base.py`
- Create: `backend/app/file_processing/processors/json_processor.py`
- Create: `backend/app/file_processing/processors/markdown_processor.py`
- Create: `backend/app/file_processing/processors/csv_processor.py`
- Create: `backend/app/file_processing/service.py`
- Create: `backend/tests/file_processing/test_file_processing_service.py`

**Step 1: Write the failing tests**

Cover:

- processor selection by file extension
- `json` files can be restored and parsed into structured data
- `.md` files can be restored and parsed into raw text
- `csv` files can be restored and parsed into header/row structures
- unsupported files fail with a stable error

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py -v
```

Expected:

- FAIL because the processing module does not exist yet

**Step 3: Write minimal implementation**

Add:

- processor base protocol or abstract class
- file processor registry
- `FileProcessingService.process_upload(upload_file)`
- UTF-8 decode helper
- normalized parsed payload creation

Implementation notes:

- keep all processors focused on file restoration and basic parsing only
- avoid business-specific extraction rules
- preserve both raw text and structured data when available

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/file_processing/test_file_processing_service.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/file_processing backend/tests/file_processing/test_file_processing_service.py
git commit -m "feat: add reusable file processing module"
```

### Task 3: Add batch ingest orchestration service

**Files:**
- Create: `backend/app/services/history_ingest_service.py`
- Create: `backend/tests/services/test_history_ingest_service.py`

**Step 1: Write the failing tests**

Cover:

- processes one uploaded file
- processes multiple uploaded files in one request
- continues on per-file failure
- returns a batch response with summary counts and per-file results

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py -v
```

Expected:

- FAIL because the ingest service does not exist yet

**Step 3: Write minimal implementation**

Add:

- `HistoryIngestService`
- `process_files(files: list[UploadFile])`

Implementation notes:

- this service owns request-level batch orchestration
- it should expose a future handoff seam such as `persist_processed_files(...)`, but leave that unimplemented or stubbed in this phase

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_history_ingest_service.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/history_ingest_service.py backend/tests/services/test_history_ingest_service.py
git commit -m "feat: add history ingest orchestration service"
```

### Task 4: Add FastAPI ingest route

**Files:**
- Create: `backend/app/api/routes/ingest.py`
- Modify: `backend/app/api/routes/__init__.py`
- Create: `backend/tests/api/routes/test_ingest_route.py`

**Step 1: Write the failing route tests**

Cover:

- `POST /api/ingest/history` accepts one file
- accepts multiple files under `files`
- returns parsed result metadata for `json`, `md`, and `csv`
- returns batch summary counts
- returns `422` when no files are supplied

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/api/routes/test_ingest_route.py -v
```

Expected:

- FAIL because the ingest route does not exist yet

**Step 3: Write minimal implementation**

Add:

- `APIRouter` for ingest
- endpoint signature using `files: list[UploadFile] = File(...)`
- route path `/ingest/history`
- delegation to `HistoryIngestService`

Implementation notes:

- do not store files on disk in v1 unless a test requires it
- read directly from uploaded streams
- keep the API response predictable for frontend consumption

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/api/routes/test_ingest_route.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/ingest.py backend/app/api/routes/__init__.py backend/tests/api/routes/test_ingest_route.py
git commit -m "feat: add history ingest api route"
```

### Task 5: Add integration coverage for end-to-end history ingest parsing

**Files:**
- Create: `backend/tests/integration/test_history_ingest_flow.py`

**Step 1: Write the failing integration test**

Cover:

- send mixed `json`, `.md`, and `csv` files in one multipart request
- server restores all three payloads correctly
- parsed batch response contains per-file outputs
- batch summary counts reflect the whole request

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/integration/test_history_ingest_flow.py -v
```

Expected:

- FAIL before full route wiring is complete

**Step 3: Write minimal implementation**

Use the existing route and service modules only. No extra business logic.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/integration/test_history_ingest_flow.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/tests/integration/test_history_ingest_flow.py
git commit -m "test: add end-to-end history ingest flow coverage"
```

### Task 6: Final verification and developer contract

**Files:**
- Modify: `backend/README.md` if present, otherwise create `backend/README.md`

**Step 1: Document the ingest contract**

Document:

- endpoint path
- multipart field name
- supported file types
- batch response shape
- current non-goals

**Step 2: Run full verification**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_schema.py tests/file_processing/test_file_processing_service.py tests/services/test_history_ingest_service.py tests/api/routes/test_ingest_route.py tests/integration/test_history_ingest_flow.py -v
```

Expected:

- all new tests PASS

**Step 3: Commit**

```bash
git add backend/README.md
git commit -m "docs: document history ingest api"
```

## Notes For The Implementer

- Prefer `UploadFile` over raw bytes in Pydantic models.
- Keep the processor API reusable outside HTTP routes.
- Use temp files or in-memory streams in tests; do not depend on real frontend uploads.
- Normalize extensions case-insensitively.
- Treat malformed file contents as per-file processing failures, not server crashes.
- Keep the route focused on ingest transport and parsing, not database writes.

## Deferred Work

Later phases can add:

- mapping parsed content to LanceDB tables
- chunking and normalization rules
- async background ingestion
- file deduplication
- upload metadata such as domain/client/source context

Plan complete and saved to `docs/plans/2026-02-28-file-upload-processing-api.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
