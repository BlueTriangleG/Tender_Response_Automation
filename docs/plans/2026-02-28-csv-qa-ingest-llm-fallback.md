# CSV QA Ingest With LLM Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the history ingest flow so batch-uploaded CSV files can be analyzed, mapped into a fixed QA record format, and written into the local LanceDB `qa_records` table. Column detection should try deterministic synonym matching first, then fall back to an LLM using the header plus first five rows. Files that still cannot be mapped should fail individually without aborting the batch.

**Architecture:** Keep `POST /api/ingest/history` as the single batch entrypoint. Narrow the ingestion pipeline for this phase to CSV-only persistence: each uploaded CSV is parsed, candidate question/answer/domain columns are inferred, rows are normalized into QA records, embeddings are generated for the QA text, and the records are upserted into LanceDB. `json` and `md` remain transport-supported only and should not be persisted in this phase.

**Tech Stack:** FastAPI, Starlette `UploadFile`, Pydantic, Python stdlib `csv`, LanceDB embedded mode, `langchain_openai.ChatOpenAI`, `langchain_openai.OpenAIEmbeddings`, pytest, `TestClient`.

---

## Recommended Design

### Option 1: Synonym-first matching with LLM fallback

This is the recommended path.

- inspect CSV headers first
- map headers using deterministic synonym lists
- if any required column is unresolved or ambiguous, call an LLM with header names plus first five rows
- require structured JSON output:
  - `{"question_col":"...", "answer_col":"...", "domain_col":"..."}`
- validate the LLM-selected columns against the actual CSV headers before using them

Why this is the right default:

- cheap and deterministic for common cases
- recoverable when real-world CSVs use odd column labels
- keeps LLM usage narrow and explainable

### Option 2: Always use the LLM for column mapping

Do not choose this.

- unnecessary latency and cost
- less deterministic
- harder to debug when simple synonym rules should have worked

### Option 3: Synonym-only, no LLM fallback

Do not choose this.

- too brittle for real customer spreadsheets
- would reject valid CSVs that only differ in naming conventions

## Fixed QA Output Contract

Every successfully mapped CSV row must be transformed into one QA-shaped record compatible with `qa_records`.

Required output fields:

- `id`
- `domain`
- `question`
- `answer`
- `text`
- `vector`
- `client`
- `source_doc`
- `tags`
- `risk_topics`
- `created_at`
- `updated_at`

Normalization rules:

- `question` comes from the detected question column
- `answer` comes from the detected answer column
- `domain` comes from the detected domain column
- `text` should be deterministic, for example:
  - `"Question: {question}\nAnswer: {answer}\nDomain: {domain}"`
- `source_doc` should be the uploaded file name
- `client`, `tags`, and `risk_topics` can start empty in this phase
- `id` should be stable per file row, for example based on file name + row index + content hash

## Column Detection Strategy

Required columns:

- question
- answer
- domain

### Phase 1: Deterministic synonym matching

Each target field should have a synonym list.

Examples:

- `question`: `question`, `prompt`, `query`, `tender_question`, `customer_question`
- `answer`: `answer`, `response`, `approved_answer`, `suggested_answer`, `historical_answer`
- `domain`: `domain`, `category`, `topic_domain`, `practice_area`

Rules:

- normalize headers case-insensitively
- strip whitespace, punctuation, and underscores before comparison
- if multiple headers match the same target, choose the first exact-priority synonym hit
- if multiple equally plausible matches remain, mark that target as ambiguous and invoke LLM fallback

### Phase 2: LLM fallback

Trigger the LLM only when:

- one or more required columns are unresolved
- or a required field has multiple plausible matches

LLM input:

- normalized header list
- original header list
- first five data rows as JSON objects

LLM output must be strict JSON:

```json
{
  "question_col": "...",
  "answer_col": "...",
  "domain_col": "..."
}
```

Validation rules:

- all returned column names must exist in the CSV
- values must be non-empty
- if validation fails, the file fails

### Phase 3: File-level failure

If deterministic matching and LLM fallback both fail:

- mark this file as failed
- include a stable failure code such as `column_mapping_failed`
- continue processing the next uploaded file

## Batch Behavior

One request may contain many files.

Recommended processing order:

1. parse each uploaded file
2. if extension is not `.csv`, mark as unsupported in this phase
3. infer QA column mapping
4. normalize rows into QA records
5. embed and upsert into `qa_records`
6. accumulate per-file success/failure results
7. return one batch response

Batch-level rule:

- one bad file must never cancel the whole request

## LanceDB Write Path

Successful CSV files should be injected into the `qa_records` table only.

Required write behavior:

- generate embeddings for each normalized QA row
- connect using the existing LanceDB bootstrap client
- upsert rows idempotently into `qa_records`
- write results should be immediately visible for later retrieval

Recommended implementation split:

- CSV processing service returns normalized QA record inputs
- QA ingestion service handles embedding + LanceDB upsert
- route returns write counts per file

## Response Contract Changes

The current ingest response should be extended to include ingestion outcomes, not just parsed payloads.

Recommended per-file additions:

- `detected_columns`
- `ingested_row_count`
- `failed_row_count`
- `storage_target`

Recommended semantics:

- `processed` means file parsed and stored successfully
- `failed` means file could not be mapped or persisted

## Implementation Tasks

### Task 1: Extend ingest schemas for CSV QA mapping and persistence results

**Files:**
- Modify: `backend/app/schemas/history_ingest.py`
- Create: `backend/tests/schemas/test_history_ingest_csv_schema.py`

**Step 1: Write the failing tests**

Cover:

- per-file result supports detected column mapping
- per-file result supports ingested row counts
- response still supports mixed file outcomes in one batch

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_csv_schema.py -v
```

Expected:

- FAIL because the new schema fields do not exist yet

**Step 3: Write minimal implementation**

Add models such as:

- `DetectedCsvColumns`
- extended `ProcessedHistoryFileResult`

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_csv_schema.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/schemas/history_ingest.py backend/tests/schemas/test_history_ingest_csv_schema.py
git commit -m "feat: extend ingest schemas for csv qa ingestion"
```

### Task 2: Add deterministic CSV header mapping

**Files:**
- Create: `backend/app/file_processing/csv_column_mapping.py`
- Create: `backend/tests/file_processing/test_csv_column_mapping.py`

**Step 1: Write the failing tests**

Cover:

- exact synonym mapping for question/answer/domain
- normalized header matching is case-insensitive
- ambiguous matches are flagged instead of guessed
- missing required targets are flagged

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/file_processing/test_csv_column_mapping.py -v
```

Expected:

- FAIL because the mapper module does not exist yet

**Step 3: Write minimal implementation**

Add:

- synonym maps
- header normalization helper
- deterministic mapper result object

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/file_processing/test_csv_column_mapping.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/file_processing/csv_column_mapping.py backend/tests/file_processing/test_csv_column_mapping.py
git commit -m "feat: add deterministic csv column mapping"
```

### Task 3: Add LLM fallback for unresolved CSV mapping

**Files:**
- Create: `backend/app/services/csv_column_detection_service.py`
- Create: `backend/tests/services/test_csv_column_detection_service.py`

**Step 1: Write the failing tests**

Cover:

- LLM fallback is called only when deterministic mapping is incomplete
- LLM receives headers plus first five rows
- invalid LLM JSON output causes file-level failure
- non-existent returned column names are rejected
- LLM exceptions are converted into file-level failure without aborting the batch

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_csv_column_detection_service.py -v
```

Expected:

- FAIL because the detection service does not exist yet

**Step 3: Write minimal implementation**

Add:

- `CsvColumnDetectionService`
- a prompt builder for header + sample rows
- structured JSON response validation

Implementation notes:

- use the LLM only as fallback
- if the LLM call fails, return a failure result for that file and continue

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_csv_column_detection_service.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/csv_column_detection_service.py backend/tests/services/test_csv_column_detection_service.py
git commit -m "feat: add llm fallback for csv column detection"
```

### Task 4: Normalize CSV rows into QA records

**Files:**
- Create: `backend/app/services/csv_qa_normalization_service.py`
- Create: `backend/tests/services/test_csv_qa_normalization_service.py`

**Step 1: Write the failing tests**

Cover:

- detected columns map CSV rows into QA-shaped records
- generated `text` is deterministic
- generated ids are stable for file + row position
- blank required fields cause row rejection

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_csv_qa_normalization_service.py -v
```

Expected:

- FAIL because the normalization service does not exist yet

**Step 3: Write minimal implementation**

Add:

- `CsvQaNormalizationService`
- row-to-QA conversion helper
- per-row skip/failure tracking

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_csv_qa_normalization_service.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/csv_qa_normalization_service.py backend/tests/services/test_csv_qa_normalization_service.py
git commit -m "feat: normalize csv rows into qa records"
```

### Task 5: Add embedding and LanceDB QA upsert service

**Files:**
- Create: `backend/app/services/qa_embedding_service.py`
- Create: `backend/app/repositories/qa_repository.py`
- Create: `backend/tests/services/test_qa_embedding_service.py`
- Create: `backend/tests/repositories/test_qa_repository.py`

**Step 1: Write the failing tests**

Cover:

- QA text batches are embedded with one configured embedding model
- normalized QA records are upserted into `qa_records`
- repeated ingests with the same ids update rather than duplicate rows

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_qa_embedding_service.py tests/repositories/test_qa_repository.py -v
```

Expected:

- FAIL because the embedding and repository modules do not exist yet

**Step 3: Write minimal implementation**

Add:

- `QaEmbeddingService`
- `QaRepository.upsert_records(...)`

Implementation notes:

- use the existing LanceDB connection helpers
- use `merge_insert(on="id")` for idempotent updates
- keep the repository limited to QA table writes in this phase

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_qa_embedding_service.py tests/repositories/test_qa_repository.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/qa_embedding_service.py backend/app/repositories/qa_repository.py backend/tests/services/test_qa_embedding_service.py backend/tests/repositories/test_qa_repository.py
git commit -m "feat: add qa embedding and lancedb upsert"
```

### Task 6: Integrate CSV QA ingestion into the existing history ingest service

**Files:**
- Modify: `backend/app/services/history_ingest_service.py`
- Modify: `backend/app/file_processing/service.py`
- Create: `backend/tests/services/test_history_ingest_csv_flow.py`

**Step 1: Write the failing tests**

Cover:

- CSV files run through parse -> map -> normalize -> embed -> upsert
- non-CSV files are reported as unsupported for persistence in this phase
- one CSV mapping failure does not stop the rest of the batch
- LLM fallback failure marks only that file failed

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_history_ingest_csv_flow.py -v
```

Expected:

- FAIL before the orchestration is wired

**Step 3: Write minimal implementation**

Update the history ingest service so it:

- accepts parsed CSV rows
- detects columns
- normalizes QA rows
- writes successful records to `qa_records`
- returns extended file-level ingest metadata

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/services/test_history_ingest_csv_flow.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/history_ingest_service.py backend/app/file_processing/service.py backend/tests/services/test_history_ingest_csv_flow.py
git commit -m "feat: integrate csv qa ingestion flow"
```

### Task 7: Add API route coverage for batch CSV ingest

**Files:**
- Modify: `backend/app/api/routes/history_ingest.py`
- Modify: `backend/tests/api/routes/test_history_ingest_route.py`
- Create: `backend/tests/integration/test_csv_history_ingest_route.py`

**Step 1: Write the failing route/integration tests**

Cover:

- batch-uploaded CSV files are persisted to QA table
- successful files return detected columns and ingested row counts
- failed files return a stable error code
- route still returns one batch response for mixed success/failure

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/api/routes/test_history_ingest_route.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:

- FAIL before route response is extended and persistence is wired

**Step 3: Write minimal implementation**

Keep the existing route path and multipart contract, but update the response to reflect true CSV ingest outcomes.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/api/routes/test_history_ingest_route.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/history_ingest.py backend/tests/api/routes/test_history_ingest_route.py backend/tests/integration/test_csv_history_ingest_route.py
git commit -m "feat: expose csv qa ingest results through api"
```

### Task 8: Final verification with real CSV samples

**Files:**
- Modify: `backend/README.md` if present, otherwise create `backend/README.md`

**Step 1: Document the CSV ingest contract**

Document:

- route path
- supported file type for persistence in this phase
- synonym-first mapping strategy
- LLM fallback behavior
- file-level failure semantics

**Step 2: Run full verification**

Run:

```bash
cd backend && ../backend/.venv/bin/pytest tests/schemas/test_history_ingest_csv_schema.py tests/file_processing/test_csv_column_mapping.py tests/services/test_csv_column_detection_service.py tests/services/test_csv_qa_normalization_service.py tests/services/test_qa_embedding_service.py tests/repositories/test_qa_repository.py tests/services/test_history_ingest_csv_flow.py tests/api/routes/test_history_ingest_route.py tests/integration/test_csv_history_ingest_route.py -v
```

Expected:

- all new tests PASS

**Step 3: Run a real-sample smoke check**

Use:

- `test_data/historical_repository/history_index.csv`
- `test_data/input/tender_questionnaire_sample.csv`

Verify:

- one file with recognizable columns ingests successfully
- one file with poor fit either uses fallback successfully or fails cleanly without breaking the batch

**Step 4: Commit**

```bash
git add backend/README.md
git commit -m "docs: document csv qa ingest flow"
```

## Notes For The Implementer

- Do not expand `json` or `md` persistence in this phase.
- Keep LLM fallback narrow and structured.
- Treat any invalid LLM output as a file-level failure.
- Do not silently guess ambiguous columns.
- Keep QA writes idempotent.

## Deferred Work

Later phases can add:

- document-table ingestion for `md` and `json`
- richer metadata extraction
- hybrid QA/document routing
- human review workflows for failed files

Plan complete and saved to `docs/plans/2026-02-28-csv-qa-ingest-llm-fallback.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
