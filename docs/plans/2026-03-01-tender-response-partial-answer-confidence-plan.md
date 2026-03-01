# Tender Response Partial Answer And Confidence Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Change tender-response behavior so truly unanswered questions carry `null` confidence fields, partially answerable questions return a partial answer with lower LLM-assigned confidence instead of being marked unanswered, and the frontend hides confidence UI for unanswered items.

**Architecture:** Split the current binary “grounded vs unanswered” decision into three states: no usable relation, partial support, and grounded support. Keep the workflow contract centered on `TenderQuestionResponse`, but refine the assessment and generation layers so `unanswered` is reserved for genuinely unrelated or unsupported questions, while partial answers stay displayable and receive lower confidence from the LLM. Update the frontend to treat confidence as optional and suppress it for unanswered results.

**Tech Stack:** FastAPI, Pydantic, LangGraph, LangChain/OpenAI structured output, React, Vitest, pytest.

---

## Recommendation

Use a **three-state answerability model**.

Recommended states:

- `no_reference`: no materially relevant evidence, return `status="unanswered"`, `generated_answer=null`, `confidence_level=null`, `confidence_reason=null`
- `partial_reference`: some relevant evidence exists but does not support a full answer, return `status="completed"`, generated partial answer, lower confidence from LLM
- `grounded`: references support the answer sufficiently, return `status="completed"`

This is better than the current behavior because it separates:

- “we know nothing useful”
- “we know something useful but not everything”
- “we can answer cleanly”

That matches your product requirement and avoids misusing `low` confidence as a proxy for “no answer”.

## Current Gaps

Current implementation behavior:

- unanswered responses are emitted with `confidence_level="low"` in [backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py)
- the frontend assumes confidence is always present and always renders a confidence badge in [frontend/src/App.tsx](/Users/autumn/Learning/interview%20questions/pans_software/frontend/src/App.tsx)
- answer generation already gives the LLM a partial/weak-support confidence rubric in [backend/app/features/tender_response/infrastructure/prompting/answer_generation.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/features/tender_response/infrastructure/prompting/answer_generation.py), but the workflow currently discards borderline answers by downgrading them to `unanswered`
- reference assessment is still binary in [backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py](/Users/autumn/Learning/interview%20questions/pans_software/backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py)

So the main work is behavioral, not visual.

## Design Decision

Do **not** implement this as a frontend-only rule and do **not** simply blank out `confidence_level` for existing unanswered paths.

Recommended backend contract change:

- keep `confidence_level: Literal["high", "medium", "low"] | None`
- keep `confidence_reason: str | None`
- standardize on `null`, not empty string, for unanswered confidence fields in API responses
- add a new grounding status such as `partial_reference`
- keep `status="completed"` for partial answers

Recommended prompt behavior:

- the LLM should explicitly produce partial answers when references support only part of the question
- missing or unsupported portions must be called out inline in parentheses inside `generated_answer`
- `confidence_reason` must explicitly explain why confidence is reduced and identify the missing or unsupported scope
- confidence should be lowered by the LLM when only partial coverage exists

## Task 1: Lock the New Response Contract with Failing Schema Tests

**Files:**
- Modify: `backend/tests/features/tender_response/test_response_schemas.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`
- Modify: `frontend/src/lib/api.test.ts`
- Modify: `frontend/src/App.test.tsx`

**Step 1: Write a failing backend schema test for unanswered confidence**

Add a test proving that an unanswered response may carry:

- `confidence_level=None`
- `confidence_reason=None`
- `generated_answer=None`

Do not plan around `""` here. Use `null` as the canonical API shape so backend and frontend can distinguish “not applicable” from “present but empty”.

Example:

```python
response = TenderQuestionResponse(
    ...,
    status="unanswered",
    grounding_status="no_reference",
    confidence_level=None,
    confidence_reason=None,
)
```

**Step 2: Write a failing backend schema test for partial answers**

Add a test proving a partial answer is allowed with:

- `status="completed"`
- `grounding_status="partial_reference"`
- non-null `generated_answer`
- low or medium confidence

**Step 3: Write failing frontend normalization tests**

Update API normalization tests so they expect:

- unanswered confidence fields may be `null`
- `partial_reference` survives JSON normalization

**Step 4: Write failing frontend rendering tests**

Add tests proving:

- unanswered rows do not render a confidence badge
- unanswered details modal does not show a confidence section
- partial answers still show a confidence badge and generated answer

**Step 5: Run tests to verify red**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_response_schemas.py tests/features/tender_response/test_tender_response_graph.py -v
```

Run:

```bash
cd frontend
npm test -- src/lib/api.test.ts src/App.test.tsx
```

Expected: FAIL because current code still assumes unanswered = low confidence and does not know `partial_reference`.

**Step 6: Commit**

```bash
git add backend/tests/features/tender_response/test_response_schemas.py backend/tests/features/tender_response/test_tender_response_graph.py frontend/src/lib/api.test.ts frontend/src/App.test.tsx
git commit -m "test: define partial answer and unanswered confidence contract"
```

## Task 2: Introduce a Three-State Reference Assessment Result

**Files:**
- Modify: `backend/app/features/tender_response/domain/models.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py`
- Modify: `backend/app/features/tender_response/infrastructure/prompting/reference_assessment.py`
- Modify: `backend/tests/features/tender_response/test_reference_assessment_service.py`

**Step 1: Write the failing assessment tests**

Add cases for:

- no references -> `no_reference`
- relevant but incomplete references -> `partial_reference`
- sufficient references -> `grounded`

The assessment result should expose enough structure to route correctly, for example:

- `answerability: Literal["none", "partial", "grounded"]`
- `grounding_status`
- `usable_reference_ids`
- `reason`

**Step 2: Update the assessment payload schema**

Refactor `_ReferenceAssessmentPayload` so the model can explicitly return partial support, not only `can_answer`.

Recommended shape:

```python
class _ReferenceAssessmentPayload(BaseModel):
    answerability: Literal["none", "partial", "grounded"]
    usable_reference_ids: list[str]
    reason: str
```

**Step 3: Update the prompt**

Change the prompt so the LLM distinguishes:

- unrelated / unsupported
- partially supported
- sufficiently supported

Add explicit instruction that:

- `none` means references are not materially relevant
- `partial` means some portion can be answered safely
- `grounded` means the answer can be fully supported

**Step 4: Implement minimal service mapping**

Map the payload to a richer `ReferenceAssessmentResult` and preserve deterministic filtering of reference ids.

**Step 5: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_reference_assessment_service.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/features/tender_response/domain/models.py backend/app/features/tender_response/infrastructure/services/reference_assessment_service.py backend/app/features/tender_response/infrastructure/prompting/reference_assessment.py backend/tests/features/tender_response/test_reference_assessment_service.py
git commit -m "refactor: add partial reference assessment state"
```

## Task 3: Teach Answer Generation to Produce Partial Answers Instead of Dropping Them

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/prompting/answer_generation.py`
- Modify: `backend/app/features/tender_response/infrastructure/services/answer_generation_service.py`
- Modify: `backend/tests/features/tender_response/test_answer_generation_service.py`

**Step 1: Write failing tests for partial answers**

Add tests proving that when the workflow enters the partial path:

- generated answer is retained
- generated answer must explicitly call out missing scope in parentheses
- confidence is low or medium, not null
- `confidence_reason` must explicitly explain why the answer is incomplete and what evidence or scope is missing

You do not need to assert exact prose; assert the prompt contract and service behavior.

**Step 2: Update the prompt contract**

Explicitly instruct the LLM:

- answer the supported portion
- do not invent unsupported details
- append unsupported or missing scope in parentheses inside `generated_answer`
- always include a concrete missing-scope note for partial answers; do not leave the gap implicit
- lower confidence when the answer is partial
- in `confidence_reason`, explicitly say the answer is partial and identify the missing certification, number, timeframe, scope, or evidence category

Recommended prompt language:

- “If references support only part of the question, answer only the supported portion and explicitly note missing or unsupported parts in parentheses within generated_answer.”
- “Do not return unanswered when a safe partial answer is possible.”
- “For any partial answer, confidence_reason must explicitly explain why confidence is reduced and what evidence or scope is missing.”

**Step 3: Keep confidence owned by the LLM**

Do not hardcode low confidence in workflow nodes for partial answers. The LLM should still emit:

- `high`
- `medium`
- `low`

based on the updated rubric, but partial answers should normally land at `low` or `medium`, not `high`.

**Step 4: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_answer_generation_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/prompting/answer_generation.py backend/app/features/tender_response/infrastructure/services/answer_generation_service.py backend/tests/features/tender_response/test_answer_generation_service.py
git commit -m "feat: support partial grounded answers with lowered confidence"
```

## Task 4: Rewire Workflow Routing So Partial Answers Stay Completed

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/routing.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/question_graph.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py`
- Modify: `backend/app/features/tender_response/infrastructure/workflows/common/builders.py`
- Modify: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Write failing graph tests**

Add graph-level tests for:

- `none` answerability -> unanswered
- `partial` answerability -> completed partial answer
- `grounded` answerability -> completed grounded answer

**Step 2: Update routing**

Current routing sends everything non-answerable to `finalize_unanswered`.

Change it so:

- `none` -> `finalize_unanswered`
- `partial` -> `generate_answer`
- `grounded` -> `generate_answer`

**Step 3: Change unanswered result building**

For unanswered results:

- `confidence_level=None`
- `confidence_reason=None`

Do not use `"low"` as a placeholder.

**Step 4: Change output downgrade behavior**

The current `assess_output` path downgrades blank/high-risk/inconsistent results to unanswered.

Refine this behavior:

- blank answer still becomes unanswered
- genuinely unsupported answer path remains unanswered
- partial-but-safe generated answers remain completed
- only unrelated/no-support cases become unanswered

If needed, encode a partial marker in `extensions` only temporarily, but prefer explicit state in `current_assessment`.

**Step 5: Add the new grounding status**

Update `TenderQuestionResponse.grounding_status` to include:

- `partial_reference`

Use it for partial answers that are returned to the user.

**Step 6: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_tender_response_graph.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/workflows/parallel/routing.py backend/app/features/tender_response/infrastructure/workflows/parallel/question_graph.py backend/app/features/tender_response/infrastructure/workflows/parallel/nodes.py backend/app/features/tender_response/infrastructure/workflows/common/builders.py backend/tests/features/tender_response/test_tender_response_graph.py backend/tests/integration/test_tender_response_route_integration.py
git commit -m "refactor: keep partial tender answers as completed results"
```

## Task 5: Update Backend Response Schemas And API Contract

**Files:**
- Modify: `backend/app/features/tender_response/schemas/responses.py`
- Modify: `backend/tests/features/tender_response/test_response_schemas.py`
- Modify: `README.md`

**Step 1: Make confidence optional in the schema**

Keep:

- `confidence_level: Literal["high", "medium", "low"] | None`
- `confidence_reason: str | None`

but ensure the documented behavior explicitly allows nulls for unanswered items.

**Step 2: Extend grounding status literal**

Add `partial_reference` to the response schema and tests.

**Step 3: Update README contract notes**

Document:

- unanswered questions return null confidence
- partial answers may be returned with `partial_reference`
- low/medium/high confidence is LLM-owned for answered content

**Step 4: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response/test_response_schemas.py tests/api/routes/test_tender_response_route.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/schemas/responses.py backend/tests/features/tender_response/test_response_schemas.py README.md
git commit -m "docs: align tender response confidence and partial answer contract"
```

## Task 6: Hide Confidence For Unanswered Items In The Frontend

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Step 1: Update frontend types**

Change:

- `confidenceLevel` to `"high" | "medium" | "low" | null`
- `confidenceReason` to `string | null`

**Step 2: Update API normalization**

Do not coerce missing/null confidence to `"low"`.

Recommended normalization:

```ts
confidenceLevel:
  question.confidence_level === "low" ||
  question.confidence_level === "medium" ||
  question.confidence_level === "high"
    ? question.confidence_level
    : null
```

**Step 3: Update table rendering**

For unanswered rows:

- show status badge
- do not show confidence badge

For completed rows:

- keep confidence badge

**Step 4: Update details modal**

If unanswered:

- either hide the confidence card entirely
- or replace it with a non-confidence explanation such as “No answer was generated”

Recommendation: hide the confidence card for unanswered items to match your requirement cleanly.

**Step 5: Run tests**

Run:

```bash
cd frontend
npm test -- src/lib/api.test.ts src/App.test.tsx
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: hide unanswered confidence in tender response ui"
```

## Task 7: Add End-to-End Partial-Answer Coverage

**Files:**
- Modify: `backend/tests/integration/test_tender_response_route_integration.py`
- Optional: `test_data/edge_case_suite/manifest.yaml`
- Optional: `test_data/edge_case_suite/expected_output/*.oracle.json`

**Step 1: Add an integration test for partial answer flow**

Use fake services to simulate:

- references relevant but incomplete
- assessment returns `partial_reference`
- generation returns a partial answer with missing scope in parentheses
- generation returns a `confidence_reason` that explicitly names the missing scope and why it prevents higher confidence
- final response remains `status="completed"`

**Step 2: Optional dataset expansion**

If you want live coverage too, add a new edge-case tender file and oracle covering:

- one partially answerable question
- expected `partial_reference`
- expected low/medium confidence
- answer includes an explicit missing-scope marker

**Step 3: Run tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/tests/integration/test_tender_response_route_integration.py test_data/edge_case_suite/manifest.yaml test_data/edge_case_suite/expected_output
git commit -m "test: cover partial tender answers end to end"
```

## Task 8: Full Verification

**Files:**
- No code changes

**Step 1: Run backend tender-response verification**

Run:

```bash
cd backend
.venv/bin/pytest tests/features/tender_response tests/api/routes/test_tender_response_route.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS.

**Step 2: Run frontend verification**

Run:

```bash
cd frontend
npm test -- src/lib/api.test.ts src/App.test.tsx
```

Expected: PASS.

**Step 3: Run static checks**

Run:

```bash
cd backend
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

Expected: PASS.

**Step 4: Commit**

```bash
git add .
git commit -m "chore: verify partial answer and confidence behavior"
```

## Notes For The Implementer

- Do not collapse partial answers back into `unanswered`.
- Do not hardcode `"low"` for unanswered anywhere in backend or frontend.
- Do not let frontend infer unanswered from missing confidence alone; use `status` and `grounding_status`.
- Keep confidence LLM-owned for answered content.
- Reserve `unanswered` for truly unrelated or unsupported cases only.
- If a partial answer is produced, `generated_answer` must explicitly include the missing scope in parentheses instead of sounding complete.
- If a partial answer is produced, `confidence_reason` must explicitly say why the answer is incomplete and what evidence is missing.
