# Backend Modular Monolith Final Architecture Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the backend into a production-grade modular monolith that stays easy to change as `history_ingest`, `agent_chat`, `retrieval`, `health`, and future capabilities grow.

**Architecture:** Use a feature-first modular monolith. Organize the codebase by business capability first, then keep layered boundaries inside each feature: `api`, `application`, `domain`, `infrastructure`, and `schemas`. Keep `shared/` small and keep third-party SDK adapters in `integrations/` unless an adapter is truly feature-local.

**Tech Stack:** FastAPI, Pydantic, pytest, OpenAI SDK, LanceDB embedded mode, LangGraph, modular monolith, feature-first packaging.

---

## Final Recommendation

Use **Option 1** as the final target architecture:

- **Deployment model:** single deployable FastAPI backend
- **Code organization:** feature-first modular monolith
- **Internal structure:** layers inside each feature
- **Shared code:** minimal and intentional
- **External SDKs:** isolated behind integration or infrastructure adapters

This is the strongest production choice for the current codebase because:

- the system is still one deployable service
- the codebase already contains multiple distinct business capabilities
- the current global `services/`, `schemas/`, `repositories/`, and `file_processing/` buckets are already mixing concerns
- microservices would add operational cost without solving the current code quality problem

## Why This Is The 2026-Stable Choice

This recommendation is aligned with stable guidance from mature software architecture sources:

- Martin Fowler continues to recommend starting with a monolith unless the team truly needs distributed-system complexity, and emphasizes making the monolith modular instead of letting it become a big ball of mud.
- Microsoft architecture guidance still frames architectural style selection around fitness for operational and structural needs, not fashion. For this backend, the cost of distributed services is unjustified while explicit module boundaries are highly justified.
- Spring Modulith is a strong 2024-2026 era reference point for a practical production monolith organized by business modules with clear boundaries, validation, and long-term maintainability.

In other words:

- do not scale the deployment model before the codebase needs it
- do scale the code organization now
- keep module boundaries explicit so future growth does not turn the backend into a bucket of global layers

## Why Not Pure Global Layers

Do **not** keep growing this structure:

```text
app/
  api/
  services/
  schemas/
  repositories/
  file_processing/
```

That structure is acceptable for a very small codebase, but it becomes weak once several business capabilities exist. The current repository is already showing that failure mode:

- [history_ingest_service.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/services/history_ingest_service.py) is acting as parser coordinator, workflow orchestrator, OpenAI caller trigger, embedding coordinator, and persistence coordinator
- [history_ingest.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/api/routes/history_ingest.py) constructs its service directly instead of depending on a composition root
- [csv_column_detection_agent.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/agents/workflows/csv_column_detection_agent.py) is really an OpenAI integration concern, not a user-facing agent workflow

Global layers optimize for file type. Production systems need to optimize for business change.

## Why Not Class-Type Grouping

Do **not** organize the codebase around class labels such as:

- all services together
- all repositories together
- all schemas together
- all clients together

That style answers the wrong question: “what kind of class is this?” rather than “which capability owns this code?”

It creates these maintenance problems:

- one feature change requires jumping across many unrelated global packages
- ownership becomes ambiguous because many features edit the same buckets
- naming degrades over time because generic names like `service.py`, `manager.py`, `processor.py`, and `repository.py` accumulate
- tests mirror the same fragmentation

## Target Architecture

```text
backend/app/
  main.py
  bootstrap/
    dependencies.py
    routers.py
  features/
    history_ingest/
      api/
        routes.py
        dependencies.py
      application/
        ingest_history_use_case.py
      domain/
        entities.py
        value_objects.py
        csv_column_mapping.py
        csv_qa_normalization.py
        errors.py
      infrastructure/
        parsers/
          csv_parser.py
          json_parser.py
          markdown_parser.py
        repositories/
          qa_lancedb_repository.py
        services/
          csv_column_detection_service.py
      schemas/
        requests.py
        responses.py
    agent_chat/
      api/
        routes.py
        dependencies.py
      application/
        chat_use_case.py
      domain/
        errors.py
      infrastructure/
        workflows/
          react_agent.py
      schemas/
        requests.py
        responses.py
    health/
      api/
        routes.py
      application/
        health_check.py
      schemas/
        responses.py
  integrations/
    openai/
      chat_completions_client.py
      embeddings_client.py
  shared/
    config/
      settings.py
    db/
      lancedb_client.py
      lancedb_bootstrap.py
    errors/
      base.py
    observability/
      logging.py
```

## Boundary Rules

Use these dependency rules without exception:

1. `api` may depend on `application`, `schemas`, and dependency providers.
2. `application` may depend on `domain` and abstracted infrastructure collaborators.
3. `domain` may depend only on Python stdlib and internal domain code.
4. `infrastructure` may depend on third-party SDKs, persistence libraries, and feature domain contracts.
5. `shared` must never absorb feature-specific logic.
6. `integrations` must not become a second dumping ground. Only put adapters there when multiple features truly share them.

## Naming Rules

Adopt naming that reflects responsibility instead of generic type labels:

- Prefer `IngestHistoryUseCase` over `HistoryIngestService`
- Prefer `QaLanceDbRepository` over `QaRepository`
- Prefer `CsvParser` over `FileProcessingService` when the code is CSV-specific
- Prefer `OpenAIEmbeddingsClient` over embedding logic hidden inside a broad service
- Prefer `dependencies.py` as the explicit composition seam instead of ad hoc direct construction in routes

Avoid broad names such as:

- `service.py`
- `manager.py`
- `utils.py`
- `processor.py`
- `helpers.py`

unless the package context makes the responsibility exact and narrow.

## Repo-Specific Mapping

These are the highest-value moves for this codebase.

### Current code to migrate first

- Move [history_ingest.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/api/routes/history_ingest.py) to `features/history_ingest/api/routes.py`
- Split [history_ingest_service.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/services/history_ingest_service.py) into:
  - `application/ingest_history_use_case.py`
  - `domain/csv_column_mapping.py`
  - `domain/csv_qa_normalization.py`
  - `infrastructure/services/csv_column_detection_service.py`
  - `infrastructure/repositories/qa_lancedb_repository.py`
- Move [history_ingest.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/schemas/history_ingest.py) to feature-local request/response schemas
- Move [csv_column_detection_agent.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/agents/workflows/csv_column_detection_agent.py) out of `agents/workflows` into either:
  - `integrations/openai/chat_completions_client.py`, or
  - `features/history_ingest/infrastructure/services/csv_column_detection_service.py` backed by an OpenAI adapter
- Move [health_service.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/services/health_service.py) into `features/health/application/health_check.py`

### Code that should remain global

- `main.py`
- app startup wiring
- root router registration
- environment configuration
- LanceDB bootstrap primitives that are truly shared

## Task 1: Establish the New Package Skeleton

**Files:**
- Create: `backend/app/bootstrap/__init__.py`
- Create: `backend/app/bootstrap/dependencies.py`
- Create: `backend/app/bootstrap/routers.py`
- Create: `backend/app/features/__init__.py`
- Create: `backend/app/features/history_ingest/__init__.py`
- Create: `backend/app/features/agent_chat/__init__.py`
- Create: `backend/app/features/health/__init__.py`
- Create: `backend/app/integrations/__init__.py`
- Create: `backend/app/shared/__init__.py`

**Step 1: Write the failing test**

Add a structure-level import test that imports the new bootstrap and feature packages.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests -k architecture_imports -v`
Expected: FAIL with import errors for missing packages.

**Step 3: Write minimal implementation**

Create empty packages and minimal importable modules.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests -k architecture_imports -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/bootstrap backend/app/features backend/app/integrations backend/app/shared backend/tests
git commit -m "refactor: add modular backend package skeleton"
```

## Task 2: Introduce a Composition Root

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/bootstrap/dependencies.py`
- Create: `backend/app/bootstrap/routers.py`
- Test: `backend/tests/integration/test_app_startup.py`

**Step 1: Write the failing test**

Add a test that verifies router registration and dependency providers come from bootstrap modules rather than direct route-local instantiation.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_app_startup.py -v`
Expected: FAIL because startup wiring still points at global route construction.

**Step 3: Write minimal implementation**

Move app-level router registration and core dependency factories into bootstrap modules.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_app_startup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/main.py backend/app/bootstrap backend/tests/integration/test_app_startup.py
git commit -m "refactor: add backend composition root"
```

## Task 3: Migrate the Health Feature First

**Files:**
- Create: `backend/app/features/health/api/routes.py`
- Create: `backend/app/features/health/application/health_check.py`
- Create: `backend/app/features/health/schemas/responses.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/routes/test_health_route.py`

**Step 1: Write the failing test**

Adjust the health route test to import the new feature-local route and schema modules.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/routes/test_health_route.py -v`
Expected: FAIL because the new modules do not exist yet.

**Step 3: Write minimal implementation**

Move health logic into the new feature package and keep the API contract unchanged.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/routes/test_health_route.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/health backend/app/main.py backend/tests/api/routes/test_health_route.py
git commit -m "refactor: move health into feature package"
```

## Task 4: Move OpenAI Adapters Out of Agent Workflows

**Files:**
- Create: `backend/app/integrations/openai/chat_completions_client.py`
- Create: `backend/app/integrations/openai/embeddings_client.py`
- Modify: `backend/app/agents/workflows/react_agent.py`
- Modify: `backend/app/agents/workflows/csv_column_detection_agent.py` or delete after migration
- Test: `backend/tests/services/test_csv_column_detection_service.py`
- Test: `backend/tests/agents/test_agent.py`

**Step 1: Write the failing test**

Add tests that assert OpenAI client behavior is injected through adapters rather than constructed in workflow code.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/services/test_csv_column_detection_service.py backend/tests/agents/test_agent.py -v`
Expected: FAIL because the workflows still instantiate SDK clients directly.

**Step 3: Write minimal implementation**

Introduce reusable OpenAI adapters and update the agent workflow and CSV column detection flow to depend on them.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/services/test_csv_column_detection_service.py backend/tests/agents/test_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/integrations/openai backend/app/agents/workflows backend/tests/services/test_csv_column_detection_service.py backend/tests/agents/test_agent.py
git commit -m "refactor: isolate openai adapters"
```

## Task 5: Migrate `history_ingest` Into a Feature Module

**Files:**
- Create: `backend/app/features/history_ingest/api/routes.py`
- Create: `backend/app/features/history_ingest/api/dependencies.py`
- Create: `backend/app/features/history_ingest/application/ingest_history_use_case.py`
- Create: `backend/app/features/history_ingest/domain/csv_column_mapping.py`
- Create: `backend/app/features/history_ingest/domain/csv_qa_normalization.py`
- Create: `backend/app/features/history_ingest/domain/entities.py`
- Create: `backend/app/features/history_ingest/domain/errors.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/csv_parser.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/json_parser.py`
- Create: `backend/app/features/history_ingest/infrastructure/parsers/markdown_parser.py`
- Create: `backend/app/features/history_ingest/infrastructure/repositories/qa_lancedb_repository.py`
- Create: `backend/app/features/history_ingest/infrastructure/services/csv_column_detection_service.py`
- Create: `backend/app/features/history_ingest/schemas/requests.py`
- Create: `backend/app/features/history_ingest/schemas/responses.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/routes/test_history_ingest_route.py`
- Test: `backend/tests/integration/test_csv_history_ingest_route.py`
- Test: `backend/tests/services/test_history_ingest_csv_flow.py`

**Step 1: Write the failing test**

Update imports in the ingest route and integration tests to use the new feature-local modules.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/routes/test_history_ingest_route.py backend/tests/integration/test_csv_history_ingest_route.py backend/tests/services/test_history_ingest_csv_flow.py -v`
Expected: FAIL because the feature-local modules do not exist yet.

**Step 3: Write minimal implementation**

Move the current ingest stack into feature-local packages while preserving API behavior.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/routes/test_history_ingest_route.py backend/tests/integration/test_csv_history_ingest_route.py backend/tests/services/test_history_ingest_csv_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/history_ingest backend/app/main.py backend/tests/api/routes/test_history_ingest_route.py backend/tests/integration/test_csv_history_ingest_route.py backend/tests/services/test_history_ingest_csv_flow.py
git commit -m "refactor: move history ingest into feature module"
```

## Task 6: Reduce or Delete the Global Buckets

**Files:**
- Modify: `backend/app/api/routes/__init__.py`
- Modify: `backend/app/services/__init__.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/repositories/__init__.py`
- Delete or deprecate legacy modules only after imports are migrated
- Test: `backend/tests`

**Step 1: Write the failing test**

Add an architecture test that forbids new feature code from importing from legacy global buckets.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests -k architecture_boundaries -v`
Expected: FAIL while legacy imports remain.

**Step 3: Write minimal implementation**

Replace remaining imports, keep temporary compatibility shims only if strictly needed, and delete dead modules once no longer referenced.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests -k architecture_boundaries -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "refactor: remove legacy global layer imports"
```

## Task 7: Mirror the New Structure in Tests

**Files:**
- Create or move tests under:
  - `backend/tests/features/history_ingest/...`
  - `backend/tests/features/agent_chat/...`
  - `backend/tests/features/health/...`
- Keep `backend/tests/integration/...` for cross-feature or app-level verification

**Step 1: Write the failing test**

Add package-level pytest collection for the new feature test tree.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features -v`
Expected: FAIL until tests are moved and imports are corrected.

**Step 3: Write minimal implementation**

Mirror the feature boundaries in the test suite and remove coupling to old global packages.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features backend/tests/integration -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests
git commit -m "test: align backend tests with feature modules"
```

## Task 8: Final Verification

**Files:**
- Verify the whole backend tree

**Step 1: Run focused tests**

```bash
pytest backend/tests/api/routes/test_health_route.py -v
pytest backend/tests/api/routes/test_history_ingest_route.py -v
pytest backend/tests/integration/test_csv_history_ingest_route.py -v
pytest backend/tests/services/test_csv_column_detection_service.py -v
pytest backend/tests/agents/test_agent.py -v
```

Expected: PASS

**Step 2: Run the broader backend suite**

```bash
pytest backend/tests -v
```

Expected: PASS

**Step 3: Perform a manual smoke check**

Run the app and verify:

- `GET /api/health`
- `POST /api/ingest/history` with a known-good CSV

**Step 4: Commit**

```bash
git add backend
git commit -m "refactor: finalize modular backend architecture"
```

## Sources

- Martin Fowler, “Monolith First” and modular monolith guidance: https://martinfowler.com/bliki/MonolithFirst.html
- Martin Fowler, “Modular Monolith”: https://martinfowler.com/bliki/ModularMonolith.html
- Microsoft Azure Architecture Center, architecture styles overview: https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/
- Spring Modulith Reference Documentation: https://docs.spring.io/spring-modulith/reference/

## Decision Summary

Use a **feature-first modular monolith** as the final backend architecture.

For this repository, the stable 2026 senior-level standard is:

- one deployable backend
- modules organized by business capability
- layers kept inside each feature
- explicit dependency boundaries
- no more growth in global `services/`, `schemas/`, and `repositories/` buckets

Plan complete and saved to `docs/plans/2026-02-28-backend-modular-monolith-architecture.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
