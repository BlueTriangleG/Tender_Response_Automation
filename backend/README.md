# Backend

FastAPI backend for the tender response automation service.

---

## Running The Backend Alone

You'll need Python 3.12+, [`uv`](https://github.com/astral-sh/uv), and an OpenAI API key.

```bash
# Install dependencies
cd backend
uv sync --group dev

# Add your OpenAI key
cp .env.example .env
# edit .env and set OPENAI_API_KEY=...

# Start the server
uv run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Alternatively, from the repo root:

```bash
npm run setup:backend
npm run dev:backend
```

---

## Environment Variables

All settings use the `PANS_BACKEND_` prefix and can be set in `backend/.env`.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. OpenAI API key. |
| `PANS_BACKEND_LANCEDB_URI` | `data/lancedb` | Path to the LanceDB directory. |
| `PANS_BACKEND_OPENAI_TENDER_RESPONSE_MODEL` | `gpt-5.2` | Model used for tender response. |
| `PANS_BACKEND_OPENAI_CSV_COLUMN_MODEL` | `gpt-4o-mini` | Model used for CSV column detection. |
| `PANS_BACKEND_OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model. |
| `PANS_BACKEND_TENDER_WORKFLOW_DEBUG` | `false` | Enable verbose workflow logging. |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/ingest/history` | Upload historical tender files |
| `POST` | `/api/tender/respond` | Submit a new tender questionnaire |

Full request/response documentation and curl examples: [docs/delivery/API_POSTMAN.md](../docs/delivery/API_POSTMAN.md).

---

## Testing

```bash
# Offline unit and integration tests (196 tests, no API key needed)
uv run pytest tests -v -m "not live_e2e"

# Live E2E suite (requires OPENAI_API_KEY in .env)
uv run pytest tests/e2e/live -m live_e2e -v

# Lint
uv run ruff check .

# Type-check
uv run mypy app
```

Or from the repo root using the npm shortcuts:

```bash
npm run test:backend
npm run test:backend:live
npm run lint:backend
npm run typecheck:backend
```
