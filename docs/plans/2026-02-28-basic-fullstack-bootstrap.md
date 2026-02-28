# Basic Full-Stack Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the most basic working repository with a React + Vite frontend and a FastAPI backend, keeping the codebases separate, adding root-level one-command development orchestration, and including layered backend tests from the start.

**Architecture:** Keep source code split into `frontend/` and `backend/`. Add a root `package.json` that only orchestrates local development commands. Structure the FastAPI backend with `main`, `controllers`, and `services`, where controllers handle HTTP and services hold business logic.

**Tech Stack:** React, Vite, JavaScript, Node.js, concurrently, Python, FastAPI, Uvicorn, pytest

---

### Task 1: Create repository scaffolding

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `package.json`
- Create: `backend/app/__init__.py`
- Create: `backend/app/controllers/__init__.py`
- Create: `backend/app/services/__init__.py`

**Step 1: Create the root ignore rules**

Add entries for:

```gitignore
node_modules/
dist/
.venv/
__pycache__/
.pytest_cache/
*.pyc
.DS_Store
```

**Step 2: Create the root README skeleton**

Include sections for:
- Project overview
- Repository structure
- Root development commands
- Frontend setup
- Backend setup
- Backend tests

**Step 3: Create the root orchestration package**

Create:

```json
{
  "name": "pans-software",
  "private": true,
  "scripts": {
    "dev": "concurrently \"npm run dev:frontend\" \"npm run dev:backend\"",
    "dev:frontend": "npm run dev --prefix frontend",
    "dev:backend": "cd backend && .venv/bin/uvicorn app.main:app --reload"
  },
  "devDependencies": {
    "concurrently": "^9.1.2"
  }
}
```

**Step 4: Create backend package markers**

Create:

```python
# backend/app/__init__.py
```

Create:

```python
# backend/app/controllers/__init__.py
```

Create:

```python
# backend/app/services/__init__.py
```

**Step 5: Commit**

```bash
git add .gitignore README.md package.json backend/app/__init__.py backend/app/controllers/__init__.py backend/app/services/__init__.py
git commit -m "chore: create base repository scaffolding"
```

### Task 2: Add a failing backend service test

**Files:**
- Create: `backend/tests/services/test_health_service.py`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Write the failing service test**

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

### Task 3: Add the minimal service layer

**Files:**
- Create: `backend/app/services/health_service.py`
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Modify: `README.md`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Create backend dependencies**

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

**Step 3: Write the minimal service**

Create:

```python
def get_health_status():
    return {"status": "ok"}
```

**Step 4: Install backend dependencies**

Run:

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Expected: dependency installation completes successfully.

**Step 5: Run test to verify it passes**

Run:

```bash
cd backend && source .venv/bin/activate && pytest tests/services/test_health_service.py -v
```

Expected: PASS for `test_get_health_status_returns_ok_payload`.

**Step 6: Update README with backend install instructions**

Document:
- how to create the virtual environment
- how to install dependencies
- how to run backend tests

**Step 7: Commit**

```bash
git add backend/app/services/health_service.py backend/requirements.txt backend/pytest.ini README.md
git commit -m "feat: add minimal backend service layer"
```

### Task 4: Add a failing backend controller test

**Files:**
- Create: `backend/tests/controllers/test_health_controller.py`
- Test: `backend/tests/controllers/test_health_controller.py`

**Step 1: Write the failing controller test**

Create:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_controller_returns_ok_response():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && source .venv/bin/activate && pytest tests/controllers/test_health_controller.py -v
```

Expected: FAIL because `app.main` and controller wiring do not exist yet.

**Step 3: Commit**

```bash
git add backend/tests/controllers/test_health_controller.py
git commit -m "test: add failing health controller test"
```

### Task 5: Add the minimal controller layer and app wiring

**Files:**
- Create: `backend/app/controllers/health_controller.py`
- Create: `backend/app/main.py`
- Modify: `README.md`
- Test: `backend/tests/controllers/test_health_controller.py`
- Test: `backend/tests/services/test_health_service.py`

**Step 1: Write the minimal controller**

Create:

```python
from fastapi import APIRouter

from app.services.health_service import get_health_status


router = APIRouter()


@router.get("/api/health")
def read_health():
    return get_health_status()
```

**Step 2: Write the FastAPI app entrypoint**

Create:

```python
from fastapi import FastAPI

from app.controllers.health_controller import router as health_router


app = FastAPI()
app.include_router(health_router)
```

**Step 3: Run controller test to verify it passes**

Run:

```bash
cd backend && source .venv/bin/activate && pytest tests/controllers/test_health_controller.py -v
```

Expected: PASS for `test_health_controller_returns_ok_response`.

**Step 4: Run service test to verify no regression**

Run:

```bash
cd backend && source .venv/bin/activate && pytest tests/services/test_health_service.py -v
```

Expected: PASS for `test_get_health_status_returns_ok_payload`.

**Step 5: Update README with backend run instructions**

Document:
- how to run `uvicorn app.main:app --reload`
- where controllers and services live

**Step 6: Commit**

```bash
git add backend/app/controllers/health_controller.py backend/app/main.py README.md
git commit -m "feat: add layered fastapi controller wiring"
```

### Task 6: Add the minimal React + Vite frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api.js`
- Modify: `README.md`

**Step 1: Create frontend package configuration**

Create:

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.14"
  }
}
```

**Step 2: Create Vite config with backend proxy**

Create:

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
```

**Step 3: Create the minimal React entrypoint**

Create:

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**Step 4: Create the API helper**

Create:

```javascript
export async function fetchHealth() {
  const response = await fetch("/api/health");

  if (!response.ok) {
    throw new Error("Failed to fetch health status.");
  }

  return response.json();
}
```

**Step 5: Create the minimal page component**

Create:

```jsx
import { useEffect, useState } from "react";
import { fetchHealth } from "./api";

export default function App() {
  const [status, setStatus] = useState("Loading...");
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadHealth() {
      try {
        const data = await fetchHealth();
        setStatus(data.status);
      } catch (loadError) {
        setError(loadError.message);
      }
    }

    loadHealth();
  }, []);

  return (
    <main>
      <h1>Full-Stack Starter</h1>
      <p>Backend status: {status}</p>
      {error ? <p>{error}</p> : null}
    </main>
  );
}
```

**Step 6: Install frontend dependencies**

Run:

```bash
cd frontend && npm install
```

Expected: React and Vite dependencies install successfully.

**Step 7: Update README with frontend instructions**

Document:
- `cd frontend && npm install`
- `npm run dev`
- Vite proxy behavior toward the backend

**Step 8: Commit**

```bash
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/src/main.jsx frontend/src/App.jsx frontend/src/api.js README.md
git commit -m "feat: add minimal react vite frontend"
```

### Task 7: Add root-level orchestration verification

**Files:**
- Modify: `README.md`

**Step 1: Install root dependencies**

Run:

```bash
npm install
```

Expected: root `concurrently` dependency installs successfully.

**Step 2: Start full-stack development from the root**

Run:

```bash
npm run dev
```

Expected:
- backend starts through `uvicorn`
- frontend starts through `vite`
- both logs appear in the same terminal session

**Step 3: Verify the browser shows the backend status**

Expected:
- page renders `Full-Stack Starter`
- page renders `Backend status: ok`

**Step 4: Finalize README quick start**

Add a concise "Quick Start" section with:
- root install
- backend install
- frontend install
- root dev command
- backend test command

**Step 5: Commit**

```bash
git add README.md package.json
git commit -m "docs: add root development workflow"
```

### Task 8: Final verification before completion

**Files:**
- No file changes required

**Step 1: Run all backend tests**

Run:

```bash
cd backend && source .venv/bin/activate && pytest -v
```

Expected: all backend tests pass.

**Step 2: Run frontend production build**

Run:

```bash
cd frontend && npm run build
```

Expected: Vite build succeeds without errors.

**Step 3: Confirm root orchestration script is still valid**

Run:

```bash
npm run dev
```

Expected: frontend and backend both start correctly from the root.

**Step 4: Review repository structure**

Run:

```bash
find . -maxdepth 4 -type f | sort
```

Expected: repository contains the documented root, frontend, and layered backend files only.

**Step 5: Commit**

```bash
git add .
git commit -m "chore: verify minimal full-stack bootstrap"
```
