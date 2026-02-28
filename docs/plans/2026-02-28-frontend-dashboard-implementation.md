# Frontend Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Vite React frontend that presents the tender-processing dashboard described in `docs/plans/frontend_design.md`.

**Architecture:** Create a standalone `frontend/` application using React and Vite. The UI will use a small typed API client that talks to the existing backend health route and falls back to structured demo data for tender processing and history panels until real backend endpoints exist.

**Tech Stack:** Vite, React, TypeScript, Vitest, React Testing Library, CSS variables

---

### Task 1: Scaffold the frontend app

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Step 1: Write the failing test**

Create a render test that expects the dashboard shell title and upload controls to exist.

**Step 2: Run test to verify it fails**

Run: `npm test --prefix frontend -- --run`
Expected: FAIL because the frontend app and test tooling do not exist yet.

**Step 3: Write minimal implementation**

Add the Vite app scaffold and render the application root.

**Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend -- --run`
Expected: PASS for the shell render test.

### Task 2: Add dashboard behaviors

**Files:**
- Create: `frontend/src/components/*`
- Create: `frontend/src/lib/*`
- Test: `frontend/src/App.test.tsx`

**Step 1: Write the failing test**

Add tests for:
- health status rendering
- processing a selected file
- mock results appearing in the result table
- summary metrics updating

**Step 2: Run test to verify it fails**

Run: `npm test --prefix frontend -- --run`
Expected: FAIL because the dashboard logic is not implemented yet.

**Step 3: Write minimal implementation**

Implement typed mock-backed services, a dashboard page, and presentational sections that satisfy the plan document.

**Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend -- --run`
Expected: PASS

### Task 3: Add visual system and production polish

**Files:**
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/*`

**Step 1: Write the failing test**

Add assertions for key content and accessible labels that reflect the final layout.

**Step 2: Run test to verify it fails**

Run: `npm test --prefix frontend -- --run`
Expected: FAIL until semantic labels and content are in place.

**Step 3: Write minimal implementation**

Implement the industrial audit visual system, responsive layout, expansion panels, risk badges, and download affordances.

**Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend -- --run`
Expected: PASS

### Task 4: Verify shipping state

**Files:**
- Modify: `README.md`

**Step 1: Run the full frontend test suite**

Run: `npm test --prefix frontend -- --run`
Expected: PASS

**Step 2: Run the production build**

Run: `npm run build --prefix frontend`
Expected: PASS

**Step 3: Document usage**

Update the repository README with the actual frontend setup and note which backend endpoints are still mocked.
