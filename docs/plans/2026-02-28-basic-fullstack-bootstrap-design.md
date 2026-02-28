# Basic Full-Stack Bootstrap Design

**Goal:** Set up a minimal full-stack repository with a React + Vite frontend and a Python FastAPI backend, keeping all code in English, supporting one-command local development from the repository root, and including backend test integration from day one.

## Current State

The repository is effectively empty. There is no existing frontend, backend, or shared tooling to preserve, so this should be designed as a clean greenfield bootstrap.

## Confirmed Requirements

- Frontend uses React + Vite.
- Backend uses Python + FastAPI.
- Code stays in English.
- Backend includes test integration.
- Frontend and backend source code remain clearly separated.
- The repository should support running both sides together from the root.
- Backend uses a layered architecture with classic separation such as controller and service layers.

## Options For Root-Level Development Orchestration

### Option 1: Root `package.json` With `concurrently`

Keep `frontend/` and `backend/` independent, and add a root `package.json` that only provides orchestration scripts such as:

- `npm run dev`
- `npm run dev:frontend`
- `npm run dev:backend`

The root script runs Vite and Uvicorn together through `concurrently`.

**Pros**
- One command to start both services
- Frontend and backend code stay physically separate
- Minimal cognitive load
- Easy for future CI or automation to reuse

**Cons**
- Adds a small Node dependency at the repository root

### Option 2: Root `Makefile`

Use `make dev` and related targets to start the frontend and backend.

**Pros**
- No extra JavaScript orchestration dependency
- Good for command discoverability

**Cons**
- Background process management is less clean
- Cross-platform behavior is weaker
- Usually ends up more brittle than `concurrently` for local full-stack dev

### Option 3: Manual Two-Terminal Workflow

Keep the root free of orchestration and run frontend and backend separately.

**Pros**
- Absolute minimum setup

**Cons**
- Does not meet the new requirement to run both together from the root

## Recommendation

Use **Option 1: Root `package.json` with `concurrently`**.

This gives you the simplest one-command developer experience while still keeping frontend and backend fully separate. The root only coordinates processes; it does not turn the codebase into a coupled application.

## Recommended Architecture

### Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   └── health_controller.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── health_service.py
│   ├── tests/
│   │   ├── controllers/
│   │   │   └── test_health_controller.py
│   │   └── services/
│   │       └── test_health_service.py
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── api.js
├── package.json
├── .gitignore
└── README.md
```

### Frontend

- React with Vite
- JavaScript instead of TypeScript for the most basic setup
- One page fetches backend health status from `/api/health`
- Frontend source remains entirely inside `frontend/`
- Vite proxies `/api` to `http://127.0.0.1:8000`

### Backend Layered Architecture

The backend should be basic, but still structurally correct.

Minimum layers:

- `main.py`
  - creates the FastAPI app
  - wires controllers into the app
- `controllers/`
  - defines HTTP routes
  - translates HTTP requests into service calls
  - returns API responses
- `services/`
  - contains business logic
  - stays independent from HTTP details

For the first pass, a repository or persistence layer is unnecessary because there is no database yet. Adding empty layers without a real use case would just create noise.

### Data Flow

For the health endpoint, the flow should be:

`HTTP request -> controller -> service -> controller response -> client`

That gives you the layered shape now, without introducing fake complexity.

### Testing Strategy

Backend test integration should cover more than a single endpoint smoke test.

Minimum test split:

- `services/test_health_service.py`
  - validates the service returns the expected business result
- `controllers/test_health_controller.py`
  - validates the FastAPI route returns `200`
  - validates the response JSON matches the expected shape

This keeps tests aligned with the layered architecture instead of testing only through the HTTP boundary.

## Non-Goals For The First Pass

- Database
- Repository layer
- Authentication
- Docker
- CI pipelines
- Shared schema generation
- State management libraries
- UI component libraries
- Production deployment configuration

## Implementation Notes

- Keep the first backend behavior intentionally small.
- Use English for endpoint names, file names, variables, and tests.
- Keep the root wrapper limited to orchestration only.
- Avoid mixing frontend code into backend folders or backend code into frontend folders.
- Favor readable composition over abstraction.
