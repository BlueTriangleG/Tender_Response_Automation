# Pan Software Tender Response Automation Service

FastAPI + LangGraph + React prototype for the Pan Software AI Engineer take-home.

The system ingests historical tender material, accepts a new tender questionnaire in Excel or CSV, and returns structured per-question responses grounded in prior answers rather than model memory.

## What This Project Needs To Do

At a high level, the service needs to do five things well:

- find relevant historical tender evidence
- answer each new question in a way that stays consistent with prior positioning
- adapt that answer to the wording and constraints of the new tender
- avoid unsupported claims and over-promising
- process a full questionnaire without letting one bad question block the rest

## Repository Details

- Backend: FastAPI feature-first modular monolith in [backend](/Users/autumn/Learning/interview%20questions/pans_software/backend)
- Frontend: React + TypeScript + Vite dashboard in [frontend](/Users/autumn/Learning/interview%20questions/pans_software/frontend)
- Local storage: embedded LanceDB directory in [data/lancedb](/Users/autumn/Learning/interview%20questions/pans_software/data/lancedb)
- Demo datasets: [test_data](/Users/autumn/Learning/interview%20questions/pans_software/test_data)
- Delivery docs:
  - Agent architecture: [AGENT_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/AGENT_ARCHITECTURE.md)
  - RAG architecture: [RAG_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/RAG_ARCHITECTURE.md)
  - API and Postman calls: [API_POSTMAN.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/API_POSTMAN.md)
  - Sample dataset guide: [test_data/README.md](/Users/autumn/Learning/interview%20questions/pans_software/test_data/README.md)
  - Docs guide: [docs/README.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/README.md)

## Technology Stack

- Backend: Python 3.12, FastAPI, Pydantic, LangGraph, LangChain OpenAI, LanceDB, Uvicorn
- Frontend: React 19, TypeScript, Vite
- Testing: Pytest, Vitest
- Tooling: uv, Ruff, mypy, npm

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── bootstrap/
│   │   ├── core/
│   │   ├── db/
│   │   ├── features/
│   │   │   ├── health/
│   │   │   ├── history_ingest/
│   │   │   ├── tender_response/
│   │   │   └── agent_chat/
│   │   ├── integrations/
│   │   ├── memory/
│   │   └── shared/
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── data/
│   └── lancedb/
├── docs/
│   ├── architecture/
│   ├── delivery/
│   └── plans/
├── test_data/
│   ├── historical_repository/
│   ├── input/
│   ├── expected_output/
│   └── edge_case_suite/
├── package.json
└── README.md
```

## Core Features

- Historical ingest for CSV, XLSX, Markdown, TXT, and JSON tender materials
- LangGraph-driven tender response generation with per-question isolation
- Shared session memory via `session_id`
- Confidence, risk, grounding, and historical alignment metadata on every question
- Session-level conflict review across completed answers
- Excel and CSV questionnaire support
- Frontend dashboard for upload, run, and result inspection

## Prerequisites

- Python `3.12+`
- Node.js `18+`
- `uv`
- An `OPENAI_API_KEY`

Before running the project:

1. Copy [backend/.env.example](/Users/autumn/Learning/interview%20questions/pans_software/backend/.env.example) to `backend/.env`
2. Add your OpenAI key:

```text
OPENAI_API_KEY=your_key_here
```

Optional frontend config:

1. Copy [frontend/.env.example](/Users/autumn/Learning/interview%20questions/pans_software/frontend/.env.example) to `frontend/.env`
2. Override `VITE_API_BASE_URL` only if your backend is not running on `http://127.0.0.1:8000`

The backend `.env` is required for the LLM-backed tender workflow and the live E2E suite.

## How To Run The Project

Recommended local flow:

```bash
npm install
npm run setup
npm run dev
```

What these commands do:

- `npm install`: installs root tooling
- `npm run setup`: installs frontend dependencies and syncs the backend `uv` environment
- `npm run dev`: starts both services

Default local URLs:

- backend: `http://127.0.0.1:8000`
- frontend: `http://127.0.0.1:5173`

Override the frontend backend target with `VITE_API_BASE_URL` if needed.

## Optional: Run Services Separately

Backend only:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run uvicorn app.main:app --reload
```

Frontend only:

```bash
cd frontend
npm run dev
```

## API Endpoints

- `GET /api/health`
- `POST /api/ingest/history`
- `POST /api/tender/respond`

Detailed request examples and Postman instructions are in [API_POSTMAN.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/API_POSTMAN.md).

## Commands To Deploy And Verify

### Local Deployment Commands

Use the startup flow in [How To Run The Project](#how-to-run-the-project):

- `npm install`
- `npm run setup`
- `npm run dev`

### Verification Commands

Full repository verification:

```bash
npm run verify
```

This runs the same basic engineering checks the repo is organized around: tests, linting, type-checking, and the frontend production build.

Backend unit/integration tests:

```bash
npm run test:backend
```

Backend lint:

```bash
npm run lint:backend
```

Backend type-check:

```bash
npm run typecheck:backend
```

Frontend tests:

```bash
npm run test:frontend
```

Frontend production build:

```bash
npm run build:frontend
```

Live E2E suite:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/e2e/live -m live_e2e -v
```

## Sample Data

Primary demo assets live in [test_data](/Users/autumn/Learning/interview%20questions/pans_software/test_data):

- Historical repository:
  - [historical_repository/](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository)
- Sample tender input:
  - [tender_questionnaire_sample.xlsx](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.xlsx)
  - [tender_questionnaire_sample.csv](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.csv)
- Example expected output:
  - [tender_response_expected.json](/Users/autumn/Learning/interview%20questions/pans_software/test_data/expected_output/tender_response_expected.json)
- Regression and live-e2e suite:
  - [edge_case_suite/](/Users/autumn/Learning/interview%20questions/pans_software/test_data/edge_case_suite)

Dataset usage details are documented in [test_data/README.md](/Users/autumn/Learning/interview%20questions/pans_software/test_data/README.md).

## How To Run A Demo

1. Start backend and frontend.
2. Ingest historical files from [test_data/historical_repository](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository).
3. Upload [tender_questionnaire_sample.xlsx](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.xlsx).
4. Review generated answers, confidence, risk, unanswered cases, and conflict flags in the UI.

## Architecture Notes

The tender response pipeline is built around a batch graph plus an isolated per-question subgraph.

- Retriever agent: retrieves top historical references from LanceDB
- Grounding assessor agent: decides `grounded`, `partial_reference`, or fallback
- Answer composer agent: generates answer, confidence, and risk metadata
- Risk guard agent: validates output, retries recoverable errors, and materializes terminal states
- Conflict reviewer agent: checks completed answers for session-level contradictions

If you want the design rather than the code walkthrough:

- workflow and agent design: [AGENT_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/AGENT_ARCHITECTURE.md)
- retrieval and grounding design: [RAG_ARCHITECTURE.md](/Users/autumn/Learning/interview%20questions/pans_software/docs/delivery/RAG_ARCHITECTURE.md)

## Notes And Limitations

- The primary output path is JSON through the API and UI.
- The workflow uses local LanceDB for demo-scale retrieval.
- Shared session memory is tied to runtime checkpoint state keyed by `session_id`.
- Live E2E tests require valid OpenAI credentials.
