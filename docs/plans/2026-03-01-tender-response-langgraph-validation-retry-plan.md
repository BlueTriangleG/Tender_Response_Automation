# Tender Response LangGraph Validation Retry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace direct failure on recoverable tender-response validation errors with a LangGraph-native correction loop that stores retry feedback in graph state, gives the LLM up to 3 correction attempts, and only fails after the retry budget is exhausted.

**Architecture:** Keep unsupported questions on the existing `finalize_unanswered` path, but treat generation-contract violations as recoverable workflow events. Extend `QuestionProcessingState` with compact retry memory fields, route `assess_output` through a conditional retry edge, and inject validation feedback plus prior invalid output back into the next generation attempt. Prefer graph-managed retries over nested service-local retries so the correction history is explicit, inspectable, and checkpointer-friendly.

**Tech Stack:** FastAPI, LangGraph, Pydantic, LangChain/OpenAI structured output, pytest.

---

## Recommendation

Use a **state-driven correction loop inside the question subgraph**.

Recommended design:

- `assess_references`
  - unsupported -> `finalize_unanswered`
  - grounded or partial -> `generate_answer`
- `generate_answer`
  - read retry context from `QuestionProcessingState`
  - inject previous validation failures into the next prompt
- `assess_output`
  - pass -> `END`
  - recoverable validation failure and attempts `< 3` -> back to `generate_answer`
  - unrecoverable or retry budget exhausted -> `fail_generation`

This is preferable to service-local retry because:

- retry reasons stay visible in graph state
- the LLM gets actionable correction feedback, not a blind rerun
- retry count is deterministic at the workflow level
- LangGraph checkpointer can persist the short-term correction memory naturally

## Official Guidance To Follow

Use these LangGraph-aligned principles while implementing:

- Keep working memory in graph state and persist it with a checkpointer for short-term memory across a thread.
- Use conditional edges and loops for recoverable reasoning or tool/output correction.
- Reserve node retry policies for transient execution failures like network/tool instability, not semantic validation failures from the LLM.

Reference docs:

- LangGraph memory overview: https://docs.langchain.com/oss/python/langgraph/add-memory
- LangGraph thinking in LangGraph: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- LangGraph graphs and conditional edges: https://docs.langchain.com/oss/python/langgraph/workflows-agents

## Current Gap Analysis

Current behavior:

- the outer batch graph already compiles with `MemorySaver` in `backend/app/features/tender_response/infrastructure/workflows/parallel/graph.py`
- the runner already invokes the graph with `thread_id=request_id` in `backend/app/features/tender_response/application/tender_response_runner.py`
- the per-question graph currently has no retry loop and always ends after one `generate_answer -> assess_output` pass
- partial-answer validation now lives in `assess_output`, but any violation becomes `failed` immediately
- `AnswerGenerationService` still contains its own rewrite retry for malformed display output, which would stack awkwardly with graph-level retries

Main architectural issue:

- retry memory is not part of `QuestionProcessingState`, so the LLM cannot be told exactly what it got wrong on the previous attempt

## Design Decision

Do **not** implement this as `for _ in range(3)` inside `AnswerGenerationService`.

Recommended implementation boundary:

- graph state owns retry count, retry feedback, and prior invalid answer
- routing logic owns whether to loop or terminate
- prompting layer renders retry context into the next generation call
- service becomes closer to single-attempt generation, not workflow orchestration

Recommended short-term memory schema additions in `QuestionProcessingState`:

- `generation_attempt_count: int`
- `generation_validation_error: str | None`
- `generation_retry_history: list[str]`
- `last_invalid_answer: str | None`
- `last_invalid_confidence_level: str | None`
- `last_invalid_confidence_reason: str | None`

Keep this memory compact and structured. Do not store full message transcripts in state.

## Task 1: Lock Retry Semantics With Failing Graph Tests

**Files:**
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`
- Modify: `backend/tests/integration/test_tender_response_route_integration.py`

**Step 1: Write a failing test for partial-answer correction retry**

Add a graph test where:

- assessment returns `partial_reference`
- first generation attempt returns:
  - missing parentheses, or
  - `confidence_level="high"`
- second generation attempt fixes the issue

Expected final behavior:

- graph loops once
- final result is `status="completed"`
- final `grounding_status="partial_reference"`
- no `failed` result is emitted

**Step 2: Write a failing test for retry budget exhaustion**

Add a graph test where all 3 attempts keep violating the partial contract.

Expected final behavior:

- graph attempts generation 3 times
- final result is `status="failed"`
- `error_message` reflects the final validation reason
- result preserves references and review context for debugging

**Step 3: Write a failing integration test for surfaced correction success**

Use fake services to simulate:

- first attempt invalid
- second attempt corrected using retry feedback

Expected API response:

- completed partial answer
- bracketed missing scope
- low or medium confidence
- no failed state

**Step 4: Run tests to verify red**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_tender_response_graph.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: FAIL because the graph currently has no retry loop.

**Step 5: Commit**

```bash
git add backend/tests/features/tender_response/test_tender_response_graph.py backend/tests/integration/test_tender_response_route_integration.py
git commit -m "test: define langgraph validation retry behavior"
```

## Task 2: Extend Question State For Correction Memory

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/workflows/common/state.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Add explicit retry-memory fields to question state**

Extend `QuestionProcessingState` with:

```python
generation_attempt_count: int
generation_validation_error: str | None
generation_retry_history: list[str]
last_invalid_answer: str | None
last_invalid_confidence_level: str | None
last_invalid_confidence_reason: str | None
```

**Step 2: Seed the new fields when dispatching a question**

In `make_process_question_node`, initialize:

- `generation_attempt_count = 0`
- `generation_validation_error = None`
- `generation_retry_history = []`
- `last_invalid_* = None`

**Step 3: Keep memory compact**

Store only the latest invalid output fields plus a small retry-history list of validation reasons. Do not append large prompt payloads or all prior references.

**Step 4: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_tender_response_graph.py -v
```

Expected: still FAIL on missing loop behavior, but state shape issues are resolved.

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/workflows/common/state.py backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py backend/tests/features/tender_response/test_tender_response_graph.py
git commit -m "refactor: add retry memory to tender question state"
```

## Task 3: Move Generation To Single-Attempt Calls And Accept Retry Context

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/services/answer_generation_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/prompting/answer_generation.py`
- Modify: `backend/tests/features/tender_response/test_answer_generation_service.py`

**Step 1: Write failing service tests for retry-context prompting**

Add tests proving:

- first attempt uses the normal prompt
- retry attempt includes:
  - attempt number
  - previous invalid answer
  - validation error
  - explicit correction instructions

**Step 2: Refactor the service contract**

Change `generate_grounded_response(...)` to accept optional retry context, for example:

```python
async def generate_grounded_response(
    *,
    question: TenderQuestion,
    usable_references: list[HistoricalReference],
    attempt_number: int,
    validation_error: str | None = None,
    last_invalid_answer: str | None = None,
    last_invalid_confidence_level: str | None = None,
    last_invalid_confidence_reason: str | None = None,
) -> GroundedAnswerResult:
```

**Step 3: Remove nested workflow-style retries from the service**

Recommendation:

- keep only minimal output sanitization if absolutely necessary
- remove the internal “retry once then fallback” orchestration from the service
- let the graph own retry count and retry reasons

If rewrite support is retained, it must stay strictly local to malformed payload rendering, not business validation retries.

**Step 4: Add retry-aware prompt construction**

In `build_answer_generation_messages`, when `attempt_number > 1`, append a retry block such as:

- `Previous invalid answer: ...`
- `Validation error: Partial answer confidence must be low or medium.`
- `Correct the output. Do not repeat the same mistake.`

For partial answers, reinforce:

- must include missing scope in parentheses
- confidence must be low or medium
- confidence_reason must name the missing evidence or scope

**Step 5: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_answer_generation_service.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/services/answer_generation_service.py backend/app/features/tender_response/infrastructure/prompting/answer_generation.py backend/tests/features/tender_response/test_answer_generation_service.py
git commit -m "refactor: make tender answer generation retry-context aware"
```

## Task 4: Add LangGraph Conditional Retry Loop

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/question_graph.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/routing.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Add a dedicated failure node**

Create a `fail_generation` node that materializes a `failed` result only after:

- retry budget is exhausted, or
- the error is unrecoverable

**Step 2: Make `assess_output` return routing signals**

Refactor `assess_output` to write:

- `generation_validation_error`
- `generation_retry_history`
- `last_invalid_*`

and then route to one of:

- `complete_result`
- `retry_generate_answer`
- `fail_generation`

If you prefer fewer nodes, `assess_output` may still build the completed result directly, but retry routing must remain conditional in the graph.

**Step 3: Add retry routing helper**

In `routing.py`, add a helper like:

```python
def route_after_output_validation(state: QuestionProcessingState) -> str:
```

Rules:

- if validation passed -> `END`
- if recoverable validation failed and `generation_attempt_count < 3` -> `generate_answer`
- else -> `fail_generation`

**Step 4: Increment attempts in generate node**

Every pass through `generate_answer` should increment `generation_attempt_count`.

**Step 5: Preserve short-term memory through state**

On retry, keep:

- prior validation reasons
- prior invalid answer snapshot

Do not discard them until the question completes or fails.

**Step 6: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_tender_response_graph.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/workflows/parallel/question_graph.py backend/app/features/tender_response/infrastructure/workflows/parallel/routing.py backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py backend/tests/features/tender_response/test_tender_response_graph.py backend/tests/integration/test_tender_response_route_integration.py
git commit -m "feat: add langgraph validation retry loop for tender answers"
```

## Task 5: Classify Recoverable Vs Unrecoverable Validation Errors

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Define recoverable validation classes**

Recoverable:

- partial answer missing parentheses
- partial answer confidence too high
- partial answer confidence reason too vague
- answer format malformed but salvageable

Unrecoverable:

- no references / unsupported path
- corrupted graph state
- repeated empty output after retry budget exhaustion

**Step 2: Encode this classification explicitly**

Do not scatter string matching around routing. Prefer a small helper like:

```python
def is_recoverable_generation_validation_error(error: str | None) -> bool:
```

**Step 3: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_tender_response_graph.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py backend/tests/features/tender_response/test_tender_response_graph.py
git commit -m "refactor: classify recoverable tender generation validation failures"
```

## Task 6: Preserve Diagnostics In API And Frontend Contracts

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.test.ts`
- Modify: `frontend/src/App.test.tsx`

**Step 1: Keep extensions and retry diagnostics in normalized frontend state**

Preserve backend `extensions` so users and downloads retain:

- `reference_assessment_reason`
- `confidence_review_reason`
- optional retry metadata if exposed later

**Step 2: Keep UI behavior unchanged for unanswered confidence**

Still hide confidence UI for `unanswered`.

**Step 3: Show failure reason clearly for retry-exhausted questions**

When the graph fails after 3 attempts, ensure the details view still shows:

- `Error message`
- references
- grounding/risk context

No new confidence UI is needed for unanswered.

**Step 4: Run tests**

Run:

```bash
cd frontend
npm test -- --run src/lib/api.test.ts src/App.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/lib/api.test.ts frontend/src/App.test.tsx
git commit -m "feat: preserve retry diagnostics in tender response ui state"
```

## Task 7: End-To-End Verification

**Files:**
- No code changes

**Step 1: Run backend verification**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response tests/api/routes/test_tender_response_route.py tests/integration/test_tender_response_route_integration.py -q
```

Expected: PASS.

**Step 2: Run frontend verification**

Run:

```bash
cd frontend
npm test -- --run src/lib/api.test.ts src/App.test.tsx
```

Expected: PASS.

**Step 3: Optional targeted manual verification**

Use the pricing question that previously failed:

- first attempt returns partial with invalid `high` confidence
- second or third attempt returns corrected partial answer
- final status should be `completed`, not `failed`

**Step 4: Commit**

```bash
git add .
git commit -m "chore: verify tender validation retry workflow"
```

## Notes For The Implementer

- Do not use LangGraph node retry policy for semantic LLM output correction. Use graph state plus conditional loop edges.
- Do not store full chat transcripts in state; store compact correction memory only.
- Do not retry unanswered paths. Retry only when assessment already says the question is answerable or partially answerable.
- Do not keep service-local multi-step retry orchestration once graph retry is in place, except for minimal malformed-payload sanitization if necessary.
- Keep retry budget explicit and fixed at 3.
- A corrected retry result should be indistinguishable from a clean first-pass success in the final API response, aside from optional diagnostic extensions.
