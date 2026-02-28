# Backend Health Route Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the minimal backend foundation for the take-home assessment using FastAPI, with only a working health route and test coverage, while preserving the future AI workflow architecture direction.

**Architecture:** Keep the first implementation to one backend vertical slice: `main -> api route -> service`. Create the full backend skeleton now so it stays consistent with the intended AI workflow architecture, including `graph`, `agents`, `repositories`, `schemas`, `db`, and `memory`, but only implement production logic for the health slice. SQLite-backed persistence is deferred until the first real persistence feature, so the skeleton exists without fake business code.

**Tech Stack:** Python, FastAPI, Uvicorn, pytest, httpx

---

### Task 1: Create the backend package skeleton

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/graph/__init__.py`
- Create: `backend/app/graph/nodes/__init__.py`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/memory/__init__.py`
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Modify: `README.md`

**Step 1: Create backend dependency file**

Create:

```text
fastapi
uvicorn[standard]
pytest
httpx
```

**Step 2: Create pytest configuration**

Create:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

**Step 3: Create backend package markers**

Create:

```python
# backend/app/__init__.py
```

Create:

```python
# backend/app/api/__init__.py
```

Create:

```python
# backend/app/api/routes/__init__.py
```

Create:

```python
# backend/app/services/__init__.py
```

Create:

```python
# backend/app/graph/__init__.py
```

Create:

```python
# backend/app/graph/nodes/__init__.py
```

Create:

```python
# backend/app/agents/__init__.py
```

Create:

```python
# backend/app/repositories/__init__.py
```

Create:

```python
# backend/app/schemas/__init__.py
```

Create:

```python
# backend/app/db/__init__.py
```

Create:

```python
# backend/app/memory/__init__.py
```

**Step 4: Create the backend README section**

Document:
- backend directory purpose
- current backend skeleton and package responsibilities
- how to create the virtual environment
- how to install backend dependencies
- how to run backend tests

**Step 5: Commit**

```bash
git add backend/app/__init__.py backend/app/api/__init__.py backend/app/api/routes/__init__.py backend/app/graph/__init__.py backend/app/graph/nodes/__init__.py backend/app/agents/__init__.py backend/app/services/__init__.py backend/app/repositories/__init__.py backend/app/schemas/__init__.py backend/app/db/__init__.py backend/app/memory/__init__.py backend/requirements.txt backend/pytest.ini README.md
git commit -m "chore: create backend fastapi scaffolding"
```

### Task 2: Add a failing health service test

**Files:**
- Create: `backend/tests/services/test_health_service.py`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Write the failing test**

Create:

```python
from app.services.health_service import get_health_status


def test_get_health_status_returns_ok_payload():
    assert get_health_status() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/services/test_health_service.py -v
```

Expected: FAIL because `app.services.health_service` does not exist yet.

**Step 3: Commit**

```bash
git add backend/tests/services/test_health_service.py
git commit -m "test: add failing health service test"
```

### Task 3: Implement the minimal health service

**Files:**
- Create: `backend/app/services/health_service.py`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Write the minimal implementation**

Create:

```python
def get_health_status():
    return {"status": "ok"}
```

**Step 2: Create the backend virtual environment**

Run:

```bash
cd backend && python3 -m venv .venv
```

Expected: `.venv` is created successfully.

**Step 3: Install backend dependencies**

Run:

```bash
cd backend && .venv/bin/pip install -r requirements.txt
```

Expected: dependency installation completes successfully.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && .venv/bin/pytest tests/services/test_health_service.py -v
```

Expected: PASS for `test_get_health_status_returns_ok_payload`.

**Step 5: Commit**

```bash
git add backend/app/services/health_service.py
git commit -m "feat: add health service"
```

### Task 4: Add a failing health route test

**Files:**
- Create: `backend/tests/api/routes/test_health_route.py`
- Test: `backend/tests/api/routes/test_health_route.py`

**Step 1: Write the failing route test**

Create:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_route_returns_ok_response():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/pytest tests/api/routes/test_health_route.py -v
```

Expected: FAIL because the FastAPI app and route wiring do not exist yet.

**Step 3: Commit**

```bash
git add backend/tests/api/routes/test_health_route.py
git commit -m "test: add failing health route test"
```

### Task 5: Implement the health route and app wiring

**Files:**
- Create: `backend/app/api/routes/health.py`
- Modify: `backend/app/main.py`
- Modify: `README.md`
- Test: `backend/tests/api/routes/test_health_route.py`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Create the health route module**

Create:

```python
from fastapi import APIRouter

from app.services.health_service import get_health_status


router = APIRouter()


@router.get("/api/health")
def read_health():
    return get_health_status()
```

**Step 2: Create the FastAPI app entrypoint**

Create:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router


app = FastAPI()
app.include_router(health_router)
```

**Step 3: Run the route test to verify it passes**

Run:

```bash
cd backend && .venv/bin/pytest tests/api/routes/test_health_route.py -v
```

Expected: PASS for `test_health_route_returns_ok_response`.

**Step 4: Run the service test to verify no regression**

Run:

```bash
cd backend && .venv/bin/pytest tests/services/test_health_service.py -v
```

Expected: PASS for `test_get_health_status_returns_ok_payload`.

**Step 5: Update README with backend run instructions**

Document:
- how to run `backend/.venv/bin/uvicorn app.main:app --reload`
- health endpoint path: `/api/health`
- current implemented slice: route plus service

**Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/routes/health.py README.md
git commit -m "feat: add fastapi health route"
```

### Task 6: Final verification before completion

**Files:**
- No file changes required

**Step 1: Run all backend tests**

Run:

```bash
cd backend && .venv/bin/pytest -v
```

Expected: all backend tests pass.

**Step 2: Start the backend server**

Run:

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
```

Expected: server starts on `http://127.0.0.1:8000`.

**Step 3: Verify the health endpoint manually**

Run:

```bash
curl -sS http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

**Step 4: Review the current backend structure**

Run:

```bash
find backend -maxdepth 4 -type f | sort
```

Expected: the backend contains the full agreed skeleton, but only the health route slice has production behavior implemented.

**Step 5: Commit**

```bash
git add .
git commit -m "chore: verify backend health route bootstrap"
```

### Task 7: Future architecture follow-up after health route

**Files:**
- No immediate file changes required

**Step 1: Record the next backend expansion order**

After the health route is complete, implement the remaining existing skeleton in this order:

1. `schemas/` for structured request and response models
2. `db/` and `repositories/` for SQLite-backed persistence
3. `graph/` for LangGraph state and nodes
4. `agents/` for retrieval, drafting, and review roles
5. `memory/` for short-term and long-term memory abstractions

**Step 2: Do not add placeholder business logic to these layers yet**

Expected: the package skeleton already exists, but no placeholder production behavior is added before the first real use case requires it.
