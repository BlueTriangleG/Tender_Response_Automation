# Tender Response LangGraph-Native LLM Refactor Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the `tender_response` feature so its LLM-backed steps use LangGraph/LangChain-native chat model interfaces instead of the custom OpenAI SDK wrapper, while moving prompts into dedicated modules outside workflow nodes and preserving current API behavior.

**Architecture:** Keep the existing `tender_response` workflow families and runner/registry structure, but replace `OpenAIChatCompletionsClient` usage in `reference_assessment` and `answer_generation` with injected `BaseChatModel` dependencies. Externalize prompt construction into `prompting/` modules and let workflow-facing components invoke model-bound structured-output calls through LangChain interfaces. This keeps the graph orchestration intact while removing model-provider coupling from tender workflow logic.

**Tech Stack:** FastAPI, Pydantic, LangGraph, LangChain Core, LangChain OpenAI, pytest, ruff.

---

## Design Decision

Recommended approach:

- keep the workflow graph and nodes as the orchestration boundary
- keep prompt text out of nodes and out of graph wiring
- replace direct OpenAI SDK wrapper usage with `langchain_openai.ChatOpenAI`
- use structured output via LangChain model interfaces for the tender workflow only

This is better than keeping the current custom SDK wrapper inside tender services because:

- prompt evolution becomes independent of graph wiring
- model provider coupling is reduced
- workflow nodes remain readable and focused on control flow
- future sequential workflow can reuse the same prompt/model abstractions

## Scope

This refactor includes:

- tender response `reference_assessment` model invocation
- tender response `answer_generation` model invocation
- dedicated prompt modules for both steps
- tests updated to mock LangChain-style structured output models
- documentation updates where tender feature structure is described

This refactor explicitly excludes:

- changing API response schema
- changing retrieval, grounding, or risk semantics
- changing history ingest or agent-chat LLM integrations
- implementing the sequential workflow

## Target Structure

```text
backend/app/features/tender_response/
  infrastructure/
    prompting/
      __init__.py
      answer_generation.py
      reference_assessment.py
    services/
      answer_generation_service.py
      reference_assessment_service.py
```

The services remain as thin capability wrappers, but:

- they no longer own prompt strings
- they no longer depend on `OpenAIChatCompletionsClient`
- they take a LangChain chat model or create one internally

## Task 1: Add Failing Tests For LangChain Model Usage

**Files:**
- Modify: `backend/tests/features/tender_response/test_answer_generation_service.py`
- Modify: `backend/tests/features/tender_response/test_reference_assessment_service.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_modules.py`

**Steps:**
1. Change tests to inject a fake LangChain-style structured-output model instead of the current fake completion client.
2. Add assertions that prompt content comes from dedicated prompt modules, not inline strings hidden in node code.
3. Add import coverage for the new `prompting/` modules.

## Task 2: Extract Prompt Modules

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/prompting/__init__.py`
- Create: `backend/app/features/tender_response/infrastructure/prompting/answer_generation.py`
- Create: `backend/app/features/tender_response/infrastructure/prompting/reference_assessment.py`

**Steps:**
1. Move answer-generation system and user prompt construction into `answer_generation.py`.
2. Move reference-assessment system and user prompt construction into `reference_assessment.py`.
3. Keep these modules deterministic and side-effect free so they are easy to unit test later.

## Task 3: Replace OpenAI SDK Wrapper In Tender Services

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/services/answer_generation_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py`

**Steps:**
1. Replace `OpenAIChatCompletionsClient` with a LangChain chat model dependency.
2. Default to `ChatOpenAI(model=settings.openai_tender_response_model)`.
3. Use structured output with typed payloads so the service no longer manually calls the custom OpenAI SDK wrapper.
4. Keep the existing rewrite/validation behavior in answer generation.

## Task 4: Keep Workflow Contracts Stable

**Files:**
- Modify only if needed: `backend/app/features/tender_response/infrastructure/workflows/parallel/graph.py`
- Modify only if needed: `backend/app/features/tender_response/infrastructure/workflows/registry.py`

**Steps:**
1. Preserve the current workflow wiring and dependency injection shape.
2. Ensure graph construction still injects answer-generation and assessment capabilities cleanly.
3. Avoid any behavior drift in node routing or summary logic.

## Task 5: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Optional: `docs/plans/2026-02-28-tender-response-multi-workflow-architecture.md`

**Steps:**
1. Update documentation to say tender workflow prompts are managed outside nodes.
2. Note that tender workflow LLM calls now use LangChain/LangGraph-style model interfaces instead of the custom OpenAI SDK wrapper.
3. Run:
   - `ruff check .`
   - `pytest tests/features/tender_response tests/api/routes/test_tender_response_route.py tests/integration/test_tender_response_route_integration.py -v`
   - `pytest tests --ignore=tests/e2e/live -v`

## Success Criteria

This refactor is successful when:

- tender workflow no longer imports the custom OpenAI chat completions wrapper
- prompts live in dedicated modules outside workflow nodes
- current tender API behavior remains unchanged
- the parallel workflow still passes all existing non-live tests
- the tender workflow is ready for a second sequential family to reuse the same prompt/model layer
