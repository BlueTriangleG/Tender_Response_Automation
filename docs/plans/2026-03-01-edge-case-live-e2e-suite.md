# Edge-Case Live E2E Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a real end-to-end test harness that ingests the `test_data/edge_case_suite` historical CSV files, runs tender-response generation with live LanceDB and live OpenAI calls, evaluates the results against oracle JSON behavior rules, and produces a clear pass/fail report.

**Architecture:** Reuse the existing FastAPI app and current feature slices instead of inventing a second execution path. The suite should be dataset-driven from `test_data/edge_case_suite/manifest.yaml`, use an isolated LanceDB directory per run, call the real `/api/ingest/history` and `/api/tender/respond` routes through `TestClient` or a small CLI harness, then compare the real JSON responses against behavioral oracles rather than exact answer text.

**Tech Stack:** Python 3.12, pytest, FastAPI TestClient, LanceDB, OpenAI API, YAML/JSON, repository-local test data

---

### Task 1: Define live-suite execution contract

**Files:**
- Create: `backend/tests/integration/test_edge_case_suite_live.py`
- Create: `backend/tests/integration/edge_case_suite/conftest.py`
- Modify: `backend/pyproject.toml`
- Reference: `test_data/edge_case_suite/manifest.yaml`
- Reference: `test_data/edge_case_suite/README.md`

**Step 1: Add a dedicated live-suite marker**

Add a pytest marker such as `live_e2e` or `openai_live`.

Expected rule:
- excluded from default test runs
- explicitly invoked by command

**Step 2: Define required runtime prerequisites**

Document and enforce:
- `OPENAI_API_KEY` present
- backend dependencies installed
- writable temporary directory for LanceDB
- network access enabled

**Step 3: Decide the execution entrypoint**

Recommendation:
- primary runner is pytest
- optional helper script can be added later only if needed

Run:
```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/integration/test_edge_case_suite_live.py -m live_e2e -v
```

Expected:
- suite is skipped cleanly when prerequisites are missing
- suite is deterministic in setup, even if model outputs vary

### Task 2: Build isolated per-run environment setup

**Files:**
- Create: `backend/tests/integration/edge_case_suite/conftest.py`
- Modify: `backend/tests/integration/test_edge_case_suite_live.py`
- Reference: `backend/app/core/config.py`
- Reference: `backend/app/main.py`

**Step 1: Create a temporary LanceDB directory fixture**

Use `tmp_path` or `tmp_path_factory` to produce a fresh DB path for every test case or test session.

**Step 2: Override app settings through environment variables**

Set:
- `PANS_BACKEND_LANCEDB_URI`
- optionally debug flags for quieter logs

**Step 3: Ensure app startup uses the isolated DB**

Instantiate `TestClient(app)` only after environment setup so lifespan bootstraps the temp DB, not the shared `./data/lancedb`.

**Step 4: Reset app dependency overrides and env after each test**

Expected:
- no cross-test leakage
- no persistent contamination of local developer data

### Task 3: Implement historical-ingest phase from manifest

**Files:**
- Create: `backend/tests/integration/edge_case_suite/manifest_loader.py`
- Modify: `backend/tests/integration/test_edge_case_suite_live.py`
- Reference: `test_data/edge_case_suite/manifest.yaml`
- Reference: `backend/app/features/history_ingest/api/routes.py`

**Step 1: Load manifest entries into typed Python structures**

Fields to read:
- historical repository files
- tender input files
- oracle path
- recommended history files

**Step 2: POST each recommended history CSV to `/api/ingest/history`**

Use the real API route with multipart upload.

**Step 3: Handle intentionally negative history files separately**

Rules:
- files like `03_ambiguous_headers.csv` should not be part of the happy-path live suite by default
- add dedicated tests that assert they fail in the expected way

**Step 4: Verify ingest responses before moving to inference**

Assert:
- ingest HTTP status is 200 for positive files
- file-level status is `processed`
- expected counts are non-zero where applicable

### Task 4: Implement tender-response execution phase

**Files:**
- Modify: `backend/tests/integration/test_edge_case_suite_live.py`
- Reference: `backend/app/features/tender_response/api/routes.py`
- Reference: `backend/app/features/tender_response/schemas/responses.py`

**Step 1: Upload each tender CSV through the real `/api/tender/respond` route**

Send:
- `file`
- stable `sessionId` per dataset case
- optional `alignmentThreshold` override when needed

**Step 2: Capture the full response JSON to disk for later inspection**

Create an artifact directory such as:
- `backend/.artifacts/edge_case_suite/<case-id>.actual.json`

**Step 3: Preserve timing and model metadata where possible**

At minimum record:
- case id
- execution timestamp
- history files used
- threshold used

Expected:
- every case produces a machine-readable actual output snapshot

### Task 5: Build oracle evaluator for behavioral assertions

**Files:**
- Create: `backend/tests/integration/edge_case_suite/oracle_evaluator.py`
- Modify: `backend/tests/integration/test_edge_case_suite_live.py`
- Reference: `test_data/edge_case_suite/expected_output/*.oracle.json`

**Step 1: Implement summary-level assertions**

Check:
- `total_questions_processed`
- allowed `overall_completion_statuses`
- min/max counts for completed/unanswered/failed

**Step 2: Implement per-question behavioral assertions**

Support:
- exact expected status
- allowed statuses
- exact or allowed grounding statuses
- generated-answer null/not-null expectations
- allowed domain tags
- minimum/maximum reference counts
- required or forbidden phrases

**Step 3: Keep assertions tolerant to wording variation**

Do not compare:
- full answer text
- exact confidence reason prose

Do compare:
- safety outcomes
- grounding behavior
- prohibited claims
- structural fields

### Task 6: Define “达标” rubric and reporting

**Files:**
- Create: `backend/tests/integration/edge_case_suite/reporting.py`
- Modify: `test_data/edge_case_suite/README.md`
- Modify: `README.md`

**Step 1: Define hard-fail rules**

Hard fail examples:
- suite crashes before completing
- ingest positive files fail unexpectedly
- oracle summary assertions fail
- forbidden certification claims appear
- supposed unanswered cases produce unsupported grounded answers

**Step 2: Define soft evaluation metrics**

Soft metrics to print in the report:
- total cases passed
- total questions evaluated
- grounded rate
- unanswered rate
- flagged/risky rate
- phrase-level policy violations

**Step 3: Emit a final human-readable report**

Recommended output:
- terminal summary
- JSON report file
- one artifact per case

**Step 4: Add an explicit suite-level success threshold**

Recommendation:
- CI pass requires zero hard failures
- soft metrics are informational at first
- only promote soft metrics to gates after a few real runs establish a baseline

### Task 7: Add targeted negative live tests

**Files:**
- Modify: `backend/tests/integration/test_edge_case_suite_live.py`
- Reference: `test_data/edge_case_suite/historical_repository/03_ambiguous_headers.csv`
- Reference: `test_data/edge_case_suite/input/06_blank_rows_only.csv`

**Step 1: Add one ingest-negative test**

Run:
- upload `03_ambiguous_headers.csv`

Assert:
- file result is failed
- error code indicates column mapping failure or ambiguity path

**Step 2: Add one zero-question tender test**

Run:
- upload `06_blank_rows_only.csv`

Assert:
- `total_questions_processed == 0`
- `overall_completion_status` is the expected empty-batch value

### Task 8: Document commands and operating modes

**Files:**
- Modify: `README.md`
- Modify: `test_data/edge_case_suite/README.md`

**Step 1: Add setup commands**

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv sync --group dev
export OPENAI_API_KEY=...
```

**Step 2: Add live-suite command**

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/integration/test_edge_case_suite_live.py -m live_e2e -v
```

**Step 3: Add cost and flakiness notes**

Document:
- suite makes real embedding and completion calls
- results can drift slightly by model version
- oracle design intentionally checks behavior, not exact prose

### Task 9: Verify the live-suite implementation

**Files:**
- Validate: `backend/tests/integration/test_edge_case_suite_live.py`
- Validate: `backend/tests/integration/edge_case_suite/*.py`

**Step 1: Run static verification**

Run:
```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/integration/test_edge_case_suite_live.py -m live_e2e --collect-only -q
```

Expected:
- tests collect successfully

**Step 2: Run one minimal live case**

Run:
```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/integration/test_edge_case_suite_live.py -m live_e2e -k exact_and_paraphrase -v
```

Expected:
- positive ingest succeeds
- tender response returns JSON
- oracle passes

**Step 3: Run the full suite**

Run:
```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/integration/test_edge_case_suite_live.py -m live_e2e -v
```

Expected:
- all intended cases execute
- final summary and artifacts are produced
