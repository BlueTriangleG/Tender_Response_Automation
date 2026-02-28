# Local LanceDB Bootstrap Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up a local embedded LanceDB database under `./data/lancedb/`, create two durable tables for QA and document evidence, and connect the backend server to this database. This phase explicitly excludes retrieval business logic, ingestion pipelines, and LangGraph integration.

**Architecture:** Keep the scope at infrastructure level only. Add backend configuration for the LanceDB directory and table names, implement a small DB bootstrap module that creates or opens the database and its two tables, and wire a startup-safe server dependency so FastAPI can connect to LanceDB in-process without any external service.

**Tech Stack:** FastAPI, Pydantic settings, LanceDB embedded mode, PyArrow schema definitions, pytest, tempfile-backed DB tests.

---

## Scope Refinement

This plan intentionally does less than the earlier RAG plan.

Included:

- create local LanceDB directory `./data/lancedb/`
- define two physical tables
- bootstrap those tables from backend code
- ensure the FastAPI server can connect to LanceDB
- verify the connection and table creation with tests

Excluded:

- retrieval APIs
- search business logic
- embeddings service
- upsert/sync pipelines
- LangGraph nodes
- prompt assembly
- ranking and filtering logic beyond table schema readiness

## Recommended Physical Layout

Use two physical tables in one local LanceDB database directory.

### Table 1: `qa_records`

Purpose:

- store historical tender QA rows
- later support alignment-style retrieval

Recommended logical schema:

- `id: str`
- `domain: str`
- `question: str`
- `answer: str`
- `text: str`
- `vector: list[float]`
- `client: str | None`
- `source_doc: str`
- `tags: list[str]`
- `risk_topics: list[str]`
- `created_at: str`
- `updated_at: str`

Notes:

- each row is one historical QA pair
- `text` remains the normalized embedding input
- `vector` exists now so the table is truly RAG-ready even if retrieval is deferred

### Table 2: `document_records`

Purpose:

- store document-derived evidence chunks such as policy files, capability writeups, and supporting material
- later support trustworthy evidence retrieval

Recommended logical schema:

- `id: str`
- `document_id: str`
- `document_type: str`
- `domain: str`
- `title: str`
- `text: str`
- `vector: list[float]`
- `source_doc: str`
- `tags: list[str]`
- `risk_topics: list[str]`
- `client: str | None`
- `chunk_index: int`
- `created_at: str`
- `updated_at: str`

Notes:

- one source document may produce multiple rows later, but this phase only creates the table
- `document_type` should support values like `policy`, `capability`, `tender_doc`, `reference`

## Design Choices

### Option 1: Two tables in one LanceDB database directory

This is the recommended path.

- keeps QA and evidence physically separate
- avoids mixing row semantics
- keeps one local storage root for backup and inspection
- leaves later retrieval/business logic cleanly split

### Option 2: One table with `record_type`

Not recommended for your revised goal.

- simpler upfront
- weaker separation between answer anchors and evidence corpus
- easier to accumulate ambiguous row semantics over time

## Responsibility Boundary

This task stops at database readiness and server connectivity.

That means the implementation should provide:

- configuration
- connection lifecycle
- table schema creation
- startup bootstrap
- smoke tests

That means the implementation should not provide:

- “search QA” service
- “search policy” service
- any business rules for domain/client filtering
- any ingestion logic from files
- any OpenAI embedding calls

## Implementation Shape

Recommended backend components:

- `app/core/config.py`
  add LanceDB path and table-name settings
- `app/db/lancedb_client.py`
  own connection and table bootstrap
- `app/db/__init__.py`
  expose public DB helpers
- `app/services/lancedb_bootstrap_service.py`
  thin orchestration layer for app startup
- `app/main.py`
  initialize LanceDB on startup

Optional but useful:

- `backend/scripts/init_lancedb.py`
  manual bootstrap for local development

## Table-Creation Strategy

Use explicit Arrow schemas from Python.

Rules:

- database path must resolve relative to the repo root
- startup should create the DB directory if missing
- startup should create missing tables if absent
- startup should not drop or overwrite existing tables
- vector columns should exist now, even though embeddings are not populated in this phase

Recommended helper functions:

- `get_lancedb_uri()`
- `get_lancedb_connection()`
- `build_qa_table_schema()`
- `build_document_table_schema()`
- `ensure_qa_table()`
- `ensure_document_table()`
- `ensure_lancedb_ready()`

## Server Connection Pattern

Use app startup, not request-time lazy initialization.

Recommended behavior:

- when FastAPI starts, call `ensure_lancedb_ready()`
- store minimal readiness state on `app.state` if useful
- fail fast on invalid DB path or invalid schema creation

Why:

- errors surface immediately during boot
- local developer setup becomes deterministic
- future services can depend on LanceDB already existing

## Implementation Tasks

### Task 1: Add LanceDB configuration

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/core/test_lancedb_settings.py`

**Step 1: Write the failing tests**

Cover:

- default LanceDB path resolves to repo-root `data/lancedb`
- default QA table name is `qa_records`
- default document table name is `document_records`

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/core/test_lancedb_settings.py -v
```

Expected:

- FAIL because the settings do not exist yet

**Step 3: Write minimal implementation**

Add:

- `Settings.lancedb_uri`
- `Settings.lancedb_qa_table_name`
- `Settings.lancedb_document_table_name`

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/core/test_lancedb_settings.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/core/test_lancedb_settings.py
git commit -m "feat: add lancedb settings"
```

### Task 2: Create the embedded LanceDB bootstrap module

**Files:**
- Create: `backend/app/db/lancedb_client.py`
- Modify: `backend/app/db/__init__.py`
- Create: `backend/tests/db/test_lancedb_client.py`

**Step 1: Write the failing tests**

Cover:

- creating the local DB directory when missing
- creating `qa_records` when absent
- creating `document_records` when absent
- reopening the same DB preserves table names

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/db/test_lancedb_client.py -v
```

Expected:

- FAIL because the bootstrap module does not exist yet

**Step 3: Write minimal implementation**

Add:

- connection helper
- explicit Arrow schema for QA table
- explicit Arrow schema for document table
- idempotent `ensure_lancedb_ready()`

Implementation notes:

- do not create any indexes yet
- do not write seed data
- keep table creation non-destructive

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/db/test_lancedb_client.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/db/lancedb_client.py backend/app/db/__init__.py backend/tests/db/test_lancedb_client.py
git commit -m "feat: bootstrap local lancedb tables"
```

### Task 3: Wire LanceDB into FastAPI startup

**Files:**
- Create: `backend/app/services/lancedb_bootstrap_service.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/services/test_lancedb_bootstrap_service.py`
- Create: `backend/tests/integration/test_app_lancedb_startup.py`

**Step 1: Write the failing tests**

Cover:

- bootstrap service calls the DB readiness function
- app startup initializes LanceDB without request traffic
- startup leaves both tables present after app creation

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/services/test_lancedb_bootstrap_service.py tests/integration/test_app_lancedb_startup.py -v
```

Expected:

- FAIL because startup bootstrap is not wired yet

**Step 3: Write minimal implementation**

Add:

- thin bootstrap service that calls `ensure_lancedb_ready()`
- startup hook in `app/main.py`
- optional `app.state.lancedb_ready = True`

Implementation notes:

- keep startup logic sync or async only as needed by FastAPI
- do not add request-time dependency injection yet

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/services/test_lancedb_bootstrap_service.py tests/integration/test_app_lancedb_startup.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/services/lancedb_bootstrap_service.py backend/app/main.py backend/tests/services/test_lancedb_bootstrap_service.py backend/tests/integration/test_app_lancedb_startup.py
git commit -m "feat: connect backend startup to lancedb"
```

### Task 4: Add a local bootstrap script

**Files:**
- Create: `backend/scripts/init_lancedb.py`
- Create: `backend/tests/integration/test_init_lancedb_script.py`

**Step 1: Write the failing smoke test**

Cover:

- running the script creates the DB directory
- running the script creates both tables

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/integration/test_init_lancedb_script.py -v
```

Expected:

- FAIL because the script does not exist yet

**Step 3: Write minimal implementation**

Add:

- a simple CLI that initializes the embedded DB and prints created/opened table names

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/integration/test_init_lancedb_script.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/scripts/init_lancedb.py backend/tests/integration/test_init_lancedb_script.py
git commit -m "feat: add lancedb init script"
```

### Task 5: Run final verification and document the bootstrap contract

**Files:**
- Create: `backend/README.md` if absent, otherwise modify it

**Step 1: Document local usage**

Document:

- local DB path
- table names
- startup behavior
- how to initialize manually
- what this phase does not implement yet

**Step 2: Run full verification**

Run:

```bash
cd backend && pytest tests/core/test_lancedb_settings.py tests/db/test_lancedb_client.py tests/services/test_lancedb_bootstrap_service.py tests/integration/test_app_lancedb_startup.py tests/integration/test_init_lancedb_script.py -v
```

Expected:

- all new tests PASS

**Step 3: Commit**

```bash
git add backend/README.md
git commit -m "docs: document local lancedb bootstrap"
```

## Notes For The Implementer

- Do not introduce retrieval repositories yet.
- Do not introduce embeddings yet.
- Do not call OpenAI in tests or startup.
- Use temp directories in tests instead of the real `./data/lancedb`.
- Keep the schemas ready for future RAG use, but stop before business logic.

## Deferred Work After This Plan

The next phase can add:

- ingestion from historical QA files
- ingestion from policy/reference documents
- vector generation
- metadata filtering rules
- QA retrieval service
- document evidence retrieval service
- LangGraph integration

Plan complete and saved to `docs/plans/2026-02-28-local-lancedb-rag.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
