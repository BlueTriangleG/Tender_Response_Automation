# Tender Response Multi-Workflow Architecture Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the `tender_response` feature so it can support multiple production-grade workflow families under one feature boundary, starting with the current parallel workflow and a future sequential workflow, without duplicating parser, retrieval, grounding, generation, and response-contract logic.

**Architecture:** Keep `tender_response` as one feature, but split it into:

- API entrypoints bound to explicit use cases
- workflow-family-specific orchestration packages
- shared workflow primitives for state, result builders, and diagnostics
- reusable infrastructure capabilities for retrieval, grounding, and generation

This avoids two common failure modes:

- one giant `tender_response_graph.py` trying to switch behavior by flags
- duplicated “parallel” and “sequential” graphs that silently drift apart

**Tech Stack:** FastAPI, Pydantic, LangGraph `StateGraph`, OpenAI SDK, LanceDB embedded mode, pytest.

---

## Recommendation

Use a **workflow-family architecture** inside the feature.

Recommended structure:

```text
backend/app/features/tender_response/
  api/
    routes/
      parallel.py
      sequential.py
    dependencies.py
  application/
    use_cases/
      process_parallel_tender_csv.py
      process_sequential_tender_csv.py
    services/
      request_preparation.py
      response_projection.py
  domain/
    models.py
    question_extraction.py
    risk_rules.py
    policies.py
  infrastructure/
    parsers/
      tender_csv_parser.py
    repositories/
      qa_alignment_repository.py
    services/
      answer_generation_service.py
      reference_assessment_service.py
      domain_tagging_service.py
    workflows/
      common/
        state.py
        builders.py
        debug.py
        types.py
      parallel/
        graph.py
        nodes.py
        routing.py
      sequential/
        graph.py
        nodes.py
        routing.py
  schemas/
    requests.py
    responses.py
```

This keeps business ownership inside one feature while making each workflow an explicit product, not a mode flag.

## Why the Current Structure Is Not Enough

The current refactor improved file size, but it still assumes one primary workflow:

- one use case is directly bound to one compiled graph
- route shape implies one processing strategy
- the `workflows/` directory is split by technical concerns, not by workflow family

That becomes brittle as soon as the sequential workflow needs:

- a different state shape
- a different termination model
- question-to-question carryover
- different routing and retry rules
- different batch summary semantics

If those differences are added into the current package, the code will trend toward flag-driven orchestration and conditional branching across multiple files. That is harder to test and harder to reason about than two explicit workflow families.

## Target Design

### 1. API Layer

Each API entrypoint should call one use case only.

Examples:

- `POST /api/tender/respond`
  - parallel workflow
- `POST /api/tender/respond-sequential`
  - sequential workflow

The route should not know graph details. It should only:

- validate input transport
- build request options
- call the correct use case
- translate domain or validation errors to HTTP

### 2. Application Layer

Application should move from one generic use case to workflow-specific use cases:

- `ProcessParallelTenderCsvUseCase`
- `ProcessSequentialTenderCsvUseCase`

Each use case should own:

- file validation
- UTF-8 decode
- parser call
- workflow invocation
- final response projection

Shared code should be extracted to application services only when it is truly common, such as:

- request state seeding
- workflow result projection to API schema

### 3. Workflow Layer

Workflow code should be split into three scopes.

**Common**

Shared across both parallel and sequential workflows:

- shared state fragments or base typed structures
- result builders
- debug and timing helpers
- utility types

**Parallel**

Owns:

- fan-out question dispatch
- map-reduce accumulation
- question-isolated processing
- batch summary for independent question execution

**Sequential**

Owns:

- single ordered traversal
- state carryover between questions
- explicit previous-answer or prior-facts handling
- sequential termination logic

The two workflow families may reuse some node helpers, but their graph wiring should remain fully separate.

### 4. Infrastructure Capability Layer

These services should remain workflow-agnostic:

- CSV parsing
- alignment retrieval
- reference assessment
- answer generation
- domain tagging

A workflow should orchestrate these capabilities, not embed their rules directly.

This makes it possible for both workflow families to reuse the same retrieval and generation stack while differing only in orchestration.

## Design Principles

1. One workflow family per package
- No “parallel vs sequential” flags inside one graph.

2. Shared logic must be capability-level or contract-level
- Shared retrieval is good.
- Shared graph routing between fundamentally different workflows is usually bad.

3. API binds to use cases, use cases bind to workflows
- This keeps FastAPI and LangGraph concerns separated cleanly.

4. Response contract remains shared
- Both workflows must return the same top-level JSON schema unless a new API explicitly defines a different contract.

5. Sequential context is an orchestration concern
- It should not leak backward into parser or repository layers.

## Migration Plan

### Task 1. Introduce Workflow Family Packages

Create:

- `infrastructure/workflows/common/`
- `infrastructure/workflows/parallel/`
- `infrastructure/workflows/sequential/`

Move the current implementation into `parallel/` plus `common/`.

At the end of this task:

- the current parallel API should still behave identically
- there should be no sequential implementation yet
- the package layout should clearly reserve a home for it

### Task 2. Split Application Use Cases

Replace the current single use case with:

- `ProcessParallelTenderCsvUseCase`
- a placeholder or scaffold for `ProcessSequentialTenderCsvUseCase`

Keep request parsing and response projection common where appropriate, but do not let the common layer pick the workflow family by flags.

### Task 3. Rework API Routing

Refactor routes so workflow selection happens at the API boundary.

Initial target:

- preserve current route behavior by wiring it to the parallel use case
- add a clearly named route slot for sequential processing, even if it remains disabled or unimplemented in the first pass

### Task 4. Define Shared Workflow Contracts

Stabilize shared workflow interfaces:

- base request state seed shape
- question result builder contract
- batch summary builder contract
- debug logging API

The goal is that both workflow families can reuse builders without sharing graph topology.

### Task 5. Add Architecture Guardrails

Add tests that enforce the new structure:

- `parallel` graph modules are importable independently
- `sequential` package exists and is importable once scaffolded
- API routes do not import infrastructure graph modules directly
- use cases are the only place that bind workflows to transport input

### Task 6. Update Documentation

Update README and architecture docs to explain:

- `tender_response` is one feature with multiple workflow families
- current production route uses the parallel workflow
- sequential workflow is a first-class architecture target, not an ad hoc extension

## Testing Strategy

Add or update tests at four levels:

1. Import structure tests
- ensure the new `common`, `parallel`, and future `sequential` packages are importable

2. Use case tests
- verify the parallel use case calls the parallel workflow only
- later verify the sequential use case calls the sequential workflow only

3. Route tests
- route delegates to the correct use case
- no direct graph coupling in the route layer

4. Integration tests
- current `POST /api/tender/respond` keeps working unchanged after the refactor

## Success Criteria

This refactor is successful when:

- the current parallel workflow still behaves the same
- the feature no longer implies a single workflow architecture
- adding a sequential workflow no longer requires editing the parallel graph files
- the API boundary, use-case boundary, and workflow-family boundary are all explicit
- future orchestration changes can be localized to one workflow family package

## Recommended Implementation Order

1. Create `workflows/common` and `workflows/parallel`
2. Move the current graph implementation into those packages without behavior changes
3. Split the application layer into workflow-specific use cases
4. Rewire the current route to the parallel use case
5. Add a sequential scaffold package and tests
6. Update docs

## Non-Goals for This Refactor

This plan does **not** include:

- implementing the sequential workflow itself
- changing the tender response JSON contract
- changing retrieval, grounding, or generation semantics
- optimizing LLM call count
- adding cross-question consistency logic

Those should happen after the feature structure is ready to host more than one workflow family cleanly.
