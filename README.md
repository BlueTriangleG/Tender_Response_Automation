# Pans Software Take-Home

## Overview

This repository contains a full-stack tender-processing prototype with a FastAPI backend and a React frontend.

The backend is now organized as a **feature-first modular monolith**. The current implemented scope includes:

- FastAPI backend bootstrap and composition root
- Health feature vertical slice
- Agent chat feature slice
- History ingest feature slice for batch file upload, CSV/XLSX QA ingestion, and MD/JSON/TXT document ingest
- Tender response feature slice for LangGraph-based CSV answer generation
- Local LanceDB embedded storage under `./data/lancedb/`
- uv-based Python project management
- React + Vite frontend tender-processing dashboard

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   ├── bootstrap/
│   │   ├── db/
│   │   ├── features/
│   │   │   ├── agent_chat/
│   │   │   ├── health/
│   │   │   ├── history_ingest/
│   │   │   └── tender_response/
│   │   ├── integrations/
│   │   │   └── openai/
│   │   ├── core/
│   │   ├── memory/
│   │   ├── shared/
│   │   │   └── db/
│   ├── tests/
│   ├── .python-version
│   ├── pyproject.toml
│   └── uv.lock
├── data/
│   └── lancedb/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   └── test/
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── package.json
└── docs/
    └── plans/
```

## Root Development

Install root dependencies:

```bash
npm install
```

Run frontend and backend together:

```bash
npm run dev
```

## Backend

The backend uses a **feature-first modular monolith**:

- `bootstrap/`: app-level wiring, router registration, and composition root concerns
- `features/`: business capabilities, organized by feature first
- `integrations/`: third-party SDK adapters shared across features
- `core/`: global settings and base configuration
- `db/`: shared database bootstrap and LanceDB primitives
- `agents/`, `memory/`: existing AI/runtime modules that are being migrated feature-by-feature

### Backend Feature Layout

Every new backend capability should start in `app/features/<feature_name>/` and follow this shape when applicable:

```text
app/features/<feature_name>/
  api/
  application/
  domain/
  infrastructure/
  schemas/
```

Responsibility rules:

- `api/`: FastAPI routes, request parsing, dependency injection
- `application/`: use cases and orchestration
- `domain/`: business rules, normalization logic, domain models
- `infrastructure/`: persistence, file parsers, SDK-backed adapters
- `schemas/`: feature-local Pydantic contracts
- `infrastructure/prompting/`: feature-local prompt builders for LLM-backed workflow steps

### Backend Contributor Rules

When adding backend code:

- Put new business logic under `app/features/`
- Keep routes thin; push orchestration into `application/`
- Keep `domain/` free of FastAPI, LanceDB, and OpenAI SDK imports
- Put reusable third-party adapters in `app/integrations/`
- Put cross-feature infrastructure such as LanceDB bootstrap under `app/shared/`
- Do not recreate global `app/services/`, `app/schemas/`, `app/repositories/`, or `app/file_processing/` buckets

### Current Feature Ownership

- `features/health/`: `/api/health`
- `features/agent_chat/`: `/api/agent/chat`
- `features/history_ingest/`: `/api/ingest/history`
- `features/tender_response/`: `/api/tender/respond`

### LanceDB

- Storage path: `./data/lancedb/`
- Mode: embedded local database directory
- This directory is ignored by git and must not be committed

## Backend Setup

Sync the backend environment with uv:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv sync --group dev
```

Run tests:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest -v
```

Run the live edge-case E2E suite:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/e2e/live -m live_e2e -v
```

The live E2E suite will load `OPENAI_API_KEY` from `backend/.env` automatically. You can still `export OPENAI_API_KEY=...` to override it for the current shell.

Run lint checks:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run ruff check .
```

Run type checks:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run mypy app
```

Run the API server:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run uvicorn app.main:app --reload
```

Health endpoint:

```text
GET /api/health
```

History ingest endpoint:

```text
POST /api/ingest/history
```

Current history-ingest behavior:

- `.csv` and `.xlsx` uploads normalize into `qa_records`
- `.md`, `.json`, and `.txt` uploads are chunked and persisted into `document_records`
- unsupported types still fail at parse or ingest-type validation

Tender response endpoint:

```text
POST /api/tender/respond
```

Expected tender response JSON always includes:

- `total_questions_processed`
- `questions[].original_question`
- `questions[].generated_answer`
- `questions[].domain_tag`
- `questions[].confidence_level`
- `questions[].confidence_reason`
- `questions[].historical_alignment_indicator`
- `questions[].risk.level`
- `questions[].risk.reason`
- `questions[].grounding_status`
- `questions[].references[].source_doc`
- `questions[].references[].matched_question`
- `questions[].references[].matched_answer`
- `summary.flagged_high_risk_or_inconsistent_responses`
- `summary.overall_completion_status`

Tender response architecture references:

- Agent responsibility matrix: `docs/architecture/tender-response-agent-definition-table.md`

Current tender reference behavior:

- The backend does not persist uploaded source files as local blobs for tender response viewing.
- Historical alignment references are returned inline in the JSON response for the current demo scale.
- Each question can include up to the top 3 qualified historical references in `questions[].references`.
- If the workflow does not find enough grounded reference support, it returns `generated_answer = null` and marks the question with `grounding_status = "no_reference"` or `grounding_status = "insufficient_reference"`.
- Tender workflow prompts are managed under `features/tender_response/infrastructure/prompting/`, not embedded inside graph nodes.
- Tender workflow LLM steps use LangChain chat-model interfaces (`ChatOpenAI.with_structured_output(...)`) rather than the custom OpenAI SDK wrapper.
- This is an intentional temporary design for low-volume demo usage.
- If the system grows, the recommended evolution is object storage for source files plus URL-style references stored in the database.

## Backend Standards

The backend uses a modern Python project toolchain:

- `uv`: dependency management, locking, and command execution
- `pyproject.toml`: single source of truth for project metadata and tool config
- `uv.lock`: reproducible dependency resolution
- `ruff`: linting and import ordering
- `mypy`: static type checking

Current backend conventions:

- feature-first packaging over global class-type buckets
- local embedded LanceDB for RAG data
- LangGraph for orchestration, with LangChain chat-model interfaces for workflow-local LLM steps
- prompt builders stored outside workflow nodes
- no global `app/services/` bucket
- limited compatibility wrappers retained temporarily only where migration is still incomplete

## Backend Verification

Run the full backend test suite:

```bash
cd backend
../backend/.venv/bin/pytest tests -v
```

## Frontend

The frontend now contains a single-page tender processing dashboard that matches the take-home brief:

- `components/`: presentational building blocks for badges, metric cards, and result rows
- `lib/`: typed contracts plus API and mock data helpers
- `App.tsx`: the dashboard composition and local state orchestration
- `styles.css`: the industrial audit-console visual system

Current endpoint behavior:

- `GET /api/health`: live backend integration
- `GET /history/status`: mocked in the frontend until the backend route exists
- `POST /tender/process`: mocked in the frontend until the backend route exists

Install frontend dependencies:

```bash
cd frontend
npm install
```

Run the frontend only:

```bash
cd frontend
npm run dev
```

Run frontend tests:

```bash
cd frontend
npm test -- --run
```

Create a production build:

```bash
cd frontend
npm run build
```
