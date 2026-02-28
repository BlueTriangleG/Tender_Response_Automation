# Pans Software Take-Home

## Overview

This repository contains a minimal full-stack take-home project.

The current implementation scope is focused on the project foundation:

- FastAPI backend skeleton rebuilt from scratch
- Health route vertical slice
- uv-based Python project management
- React + Vite frontend tender-processing dashboard
- Mock-backed tender processing flow for interview demos while backend routes are pending

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── agents/
│   │   ├── core/
│   │   ├── db/
│   │   ├── graph/
│   │   │   └── nodes/
│   │   ├── memory/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   └── services/
│   ├── tests/
│   ├── .python-version
│   ├── pyproject.toml
│   └── uv.lock
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

The backend follows a lightweight AI workflow-oriented skeleton:

- `api/`: FastAPI routes and HTTP layer
- `core/`: application settings and shared configuration
- `services/`: business logic used by routes and workflows
- `repositories/`: future persistence access layer
- `schemas/`: request and response schemas
- `db/`: SQLite session and model modules
- `graph/`: future LangGraph state and node orchestration
- `agents/`: future agent-specific modules
- `memory/`: future short-term and long-term memory modules

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

## Backend Standards

The backend now uses a modern Python project toolchain:

- `uv`: dependency management, locking, and command execution
- `pyproject.toml`: single source of truth for project metadata and tool config
- `uv.lock`: reproducible dependency resolution
- `ruff`: linting and import ordering
- `mypy`: static type checking

The first implemented backend slice is:

- `app.main`: FastAPI application bootstrap
- `app.api.routes.health`: `/api/health` route
- `app.services.health_service`: health business logic
- `app.schemas.health`: typed response model

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
