# Pan Software — Tender Response Automation

A take-home prototype for the Pan Software AI Engineer role.

The system lets a team ingest their historical tender materials (past Q&As, policy docs, compliance records), then upload a new questionnaire and get back structured, grounded answers for each question — answers tied to real prior evidence rather than model hallucination.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3A5E?style=for-the-badge&logo=langchain&logoColor=white)
![LanceDB](https://img.shields.io/badge/LanceDB-00A3E0?style=for-the-badge&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)

---

## Demo

**History ingest** — uploading historical tender materials into the repository:

![History ingest demo](public/tender%20repository.gif)

**Tender response** — submitting a new questionnaire and reviewing grounded answers:

![Tender response demo](public/tender%20response.gif)

---

## The Problem It Solves

Responding to a tender questionnaire is repetitive, high-stakes work. The same questions appear across tenders. The answers need to stay consistent with past commitments. A wrong or contradictory answer in a live submission has real consequences.

This prototype addresses that by treating the historical archive as the source of truth and the LLM as a reasoning layer on top of it — not the other way around.

---

## Quick Start

You'll need Python 3.12+, Node 18+, `uv`, and an OpenAI API key.

```bash
# 1. Clone and install dependencies
npm install
npm run setup

# 2. Add your OpenAI key
cp backend/.env.example backend/.env
# edit backend/.env and set OPENAI_API_KEY=...

# 3. Start both services
npm run dev
```

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

To run a quick demo, ingest the sample historical files from `test_data/historical_repository/`, then upload `test_data/input/tender_questionnaire_sample.xlsx` through the UI.

---

## How It Works

**History ingest** accepts CSV, XLSX, Markdown, JSON, and TXT files. Each file is parsed, normalized into Q&A records or document chunks, embedded with `text-embedding-3-small`, and stored in a local LanceDB table. The process is idempotent — re-ingesting the same file won't create duplicates.

**Tender response** takes a new questionnaire, splits it into individual questions, and processes them in parallel through a four-stage pipeline:

1. **Retrieval** — vector search over the historical Q&A and document tables to find the most relevant prior evidence
2. **Grounding assessment** — the LLM decides whether the retrieved references are sufficient to ground an answer, or whether the question should be flagged as unanswerable
3. **Answer generation** — if grounded, the LLM drafts an answer constrained to the retrieved evidence, with confidence and risk metadata
4. **Conflict review** — once all questions are answered, a separate pass checks for contradictions across the full session

Each question runs in its own subgraph, so a failure on one doesn't stall the rest of the batch.

---

## Key Design Decisions

**LangGraph for orchestration** — the per-question isolation and the batch/subgraph structure came naturally from LangGraph's state model. The alternative was a manual asyncio fan-out, but having explicit state transitions makes the pipeline easier to inspect and extend. The conflict review step, which needs to see all completed answers before running, would have been awkward to coordinate without a graph.

**LanceDB as the vector store** — the embedded model was the right fit here: no infra to spin up, runs alongside the API process, supports both vector search and metadata filtering. For a production deployment this would likely swap to a managed store, but it doesn't change the interface.

**Feature-first module layout** — each feature (`history_ingest`, `tender_response`) owns its full stack from routes down to repositories. This makes it easy to trace any behaviour end-to-end and keeps cross-feature coupling explicit. The alternative (layer-first grouping) tends to scatter related logic across the codebase as the project grows.

**Grounding before generation** — the reference assessment step runs before the LLM drafts any answer. This means the model is never asked to generate from insufficient evidence; it either gets a vetted reference set or returns a structured "can't answer" rather than a confident guess.

---

## Repository Layout

```
backend/          FastAPI app (feature-first modular monolith)
  app/
    features/
      health/
      history_ingest/     # ingest pipeline
      tender_response/    # response workflow
    core/                 # config and settings
    db/                   # LanceDB client and schema
    integrations/         # OpenAI wrappers
    shared/               # bootstrap utilities
  tests/                  # 196 tests, offline by default

frontend/         React 19 + TypeScript + Vite dashboard

data/lancedb/     embedded vector store (created on first run)

test_data/
  historical_repository/  sample history files for demo ingest
  input/                  sample tender questionnaires
  expected_output/        reference outputs for manual comparison
  edge_case_suite/        regression cases for the live E2E suite

docs/delivery/    architecture writeups (agent design, RAG, memory/state, API)
```

---

## Testing

### Offline suite (default)

Runs 196 unit and integration tests with no external dependencies:

```bash
npm run test:backend
```

### Live E2E suite

Runs the full edge-case regression suite against a real OpenAI-backed stack. Each case ingests a curated history file, submits a tender questionnaire, and evaluates the response against a pre-defined oracle.

Requires `OPENAI_API_KEY` set in `backend/.env` and the backend running:

```bash
npm run test:backend:live
```

Artifacts (per-case actual output, oracle diff, pass/fail CSV) are written to `backend/.artifacts/edge_case_suite/` after each run. This makes it easy to diff results across runs or inspect exactly what the model produced for any failing case.

Edge case inputs and expected oracles live in `test_data/edge_case_suite/`.

### Full verification

Tests + lint + type-check + frontend build in one command:

```bash
npm run verify
```

---

## API

Three endpoints: `GET /api/health`, `POST /api/ingest/history`, `POST /api/tender/respond`.

Full curl examples, field references, sample payloads, and Postman setup are in [docs/delivery/API_POSTMAN.md](docs/delivery/API_POSTMAN.md).

---

## Further Reading

The design decisions above are expanded in the delivery docs:

- [Agent and workflow architecture](docs/delivery/AGENT_ARCHITECTURE.md)
- [RAG and retrieval design](docs/delivery/RAG_ARCHITECTURE.md)
- [Memory and session state](docs/delivery/MEMORY_AND_STATE.md)

---

## Known Limitations

Session memory uses an in-process checkpoint store, so state doesn't survive a server restart. For a production version this would be replaced with a persistent backend. The rest of the architecture is designed to be storage-agnostic so that swap is contained to a single wiring point.
