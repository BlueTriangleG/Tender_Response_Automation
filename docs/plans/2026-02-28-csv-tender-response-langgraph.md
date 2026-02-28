# CSV Tender Response LangGraph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a demo-ready backend flow that accepts a new tender CSV file, processes any number of questions through a LangGraph workflow, and returns structured JSON answers with per-question results and a final summary.

**Architecture:** Use a feature-first workflow under a new `tender_response` feature. Parse the CSV into a list of question items, run a LangGraph Graph API workflow with state-driven per-question processing and conditional branching for historical-match vs no-match paths, and aggregate results into a single JSON response. Reuse the existing local LanceDB `qa_records` table for historical alignment retrieval, but keep the workflow isolated from export/file-generation concerns in this phase.

**Tech Stack:** FastAPI, Pydantic, LangGraph Graph API, OpenAI SDK / LangChain OpenAI model adapter, LanceDB embedded mode, pytest.

---

## Brainstormed Recommendation

Use a **two-layer approach**:

- **API/application layer** handles CSV upload, parsing, request/session setup, and final JSON response.
- **LangGraph workflow layer** handles question-by-question answer generation, confidence/flagging decisions, conditional branching, and final reduction into a summary.

This is better than putting all logic in one giant service because:

- the workflow becomes testable as a graph, not a script
- per-question failures can be isolated cleanly
- historical match branching stays explicit
- future export steps can be added after the graph without redesigning the core

## Response Contract Decision

The response must be designed as a **stable, extensible JSON contract**.

That means:

- the top-level response must always include batch summary fields the frontend can depend on
- each question result must always include the required five business fields
- future enhancements must fit into additive fields such as `flags`, `metadata`, and `extensions`
- we should avoid making the required business fields optional unless the whole question failed

Recommended contract shape:

```json
{
  "request_id": "uuid",
  "session_id": "uuid-or-client-session",
  "source_file_name": "tender_questions.csv",
  "total_questions_processed": 12,
  "questions": [
    {
      "question_id": "q-001",
      "original_question": "Do you support TLS 1.2 or above?",
      "generated_answer": "Yes. Production traffic is restricted to TLS 1.2 or higher.",
      "domain_tag": "security",
      "confidence_level": "high",
      "historical_alignment_indicator": true,
      "status": "completed",
      "flags": {
        "high_risk": false,
        "inconsistent_response": false
      },
      "metadata": {
        "source_row_index": 0,
        "alignment_record_id": "qa_xxx",
        "alignment_score": 0.89
      },
      "error_message": null,
      "extensions": {}
    }
  ],
  "summary": {
    "total_questions_processed": 12,
    "flagged_high_risk_or_inconsistent_responses": 2,
    "overall_completion_status": "completed_with_flags"
  }
}
```

This satisfies your current required fields while preserving room for:

- citations or evidence later
- additional risk categories
- reviewer annotations
- export metadata
- downstream scoring or routing signals

## Scope for This Phase

This phase includes:

- CSV input only
- dynamic handling of any number of questions
- JSON response only
- per-question structured output
- final batch summary
- LangGraph state + short-term thread/session memory
- historical QA alignment lookup from local LanceDB

This phase explicitly excludes:

- Excel output generation
- CSV output generation
- document-table evidence retrieval
- frontend UI work
- persistent long-term conversational memory

## Expected Input and Output

### Input

- One CSV file containing tender questions
- 10-20 questions in typical demo usage, but no hard-coded question limit
- Mixed domains
- Some questions may contain strict compliance wording

### Output JSON

For each question:

- `original_question`
- `generated_answer`
- `domain_tag`
- `confidence_level`
- `historical_alignment_indicator`

Also include stable operational fields per question:

- `question_id`
- `status`
- `flags`
- `metadata`
- `error_message`
- `extensions`

Final summary:

- `total_questions_processed`
- `flagged_high_risk_or_inconsistent_responses`
- `overall_completion_status`

Top-level response should also include:

- `request_id`
- `session_id`
- `source_file_name`
- `questions`
- `summary`

## Recommended Feature Structure

```text
backend/app/features/tender_response/
  api/
    routes.py
    dependencies.py
  application/
    process_tender_csv_use_case.py
  domain/
    models.py
    question_extraction.py
    risk_rules.py
  infrastructure/
    parsers/
      tender_csv_parser.py
    repositories/
      qa_alignment_repository.py
    services/
      answer_generation_service.py
      domain_tagging_service.py
      confidence_service.py
    workflows/
      tender_response_graph.py
  schemas/
    requests.py
    responses.py
```

## LangGraph Design

Use the **Graph API**, not the existing generic agent wrapper.

Reasoning:

- official LangGraph guidance for stateful workflows centers on `StateGraph`, conditional edges, reducers, and `Send` for map-reduce style fan-out
- this task is a deterministic workflow with bounded nodes, not an open-ended agent loop
- per-question branching and final aggregation fit the Graph API directly

### State Model

Use a Pydantic or `TypedDict` state with these keys:

- `session_id`
- `source_file_name`
- `questions`
- `question_results`
- `summary`
- `run_errors`
- `extensions`

Use reducer semantics on `question_results` and `run_errors` so parallel/per-question results accumulate cleanly.

### Node Topology

1. `extract_questions`
- Parse CSV rows into normalized question items.

2. `dispatch_questions`
- Fan out one graph execution per question using `Send`.

3. `retrieve_alignment`
- Query LanceDB `qa_records` by semantic similarity.

4. `route_alignment`
- Conditional branch:
  - `historical_match`
  - `no_historical_match`

5. `generate_answer_with_alignment`
- Use historical answer as alignment context.

6. `generate_answer_without_alignment`
- Generate answer without historical anchor, under stricter fallback rules.

7. `assess_output`
- Assign domain tag, confidence level, historical alignment indicator, risk flags, and inconsistency flags.

8. `finalize_question`
- Emit one per-question result object, even on failure.

9. `summarize_batch`
- Reduce all question results into one batch summary.

10. `END`

### Failure Handling

- Any one question failure produces a failed per-question result
- Graph execution continues for other questions
- Final status becomes:
  - `completed`
  - `completed_with_flags`
  - `partial_failure`
  - `failed`

## Historical Match Strategy

For this phase, use only `qa_records`.

Retrieval output should provide:

- `matched`: boolean
- `matched_record_id`
- `matched_question`
- `matched_answer`
- `similarity_score`

Branching rule:

- if similarity >= configured threshold: use alignment path
- else: use no-match path

This directly satisfies the required “conditional branching for no historical match vs historical matching.”

## Guardrails and Non-Fabrication

To satisfy “no fabricated certifications or unsupported claims,” add these workflow rules:

- if no historical match exists, the answer generator must prefer conservative wording
- if the generated content implies a certification, SLA, or compliance claim not present in historical alignment context, mark the question as `high_risk`
- final response must preserve a per-question flag for:
  - `high_risk`
  - `inconsistent_with_history`

Recommended response-field mapping:

- `flags.high_risk`
- `flags.inconsistent_response`
- `summary.flagged_high_risk_or_inconsistent_responses`

Do not rely on prompt wording alone. Also encode deterministic post-generation checks in Python.

## API Design

Add a new route:

- `POST /api/tender/respond`

Request:

- `multipart/form-data`
- one CSV file
- optional `session_id`
- optional `alignment_threshold`

Response:

- JSON only in this phase
- full per-question results
- summary block
- stable extensible shape suitable for later export and enrichment

## Task 1: Add Request and Response Contracts

**Files:**
- Create: `backend/app/features/tender_response/schemas/requests.py`
- Create: `backend/app/features/tender_response/schemas/responses.py`
- Test: `backend/tests/features/tender_response/test_response_schemas.py`

**Step 1: Write the failing test**

Add tests for:

- per-question result schema
- final batch summary schema
- top-level response schema
- additive extensibility fields such as `flags`, `metadata`, and `extensions`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features/tender_response/test_response_schemas.py -v`
Expected: FAIL because the new schemas do not exist.

**Step 3: Write minimal implementation**

Create the Pydantic models for:

- question result
- batch summary
- top-level tender response payload

Required question-result fields:

- `original_question`
- `generated_answer`
- `domain_tag`
- `confidence_level`
- `historical_alignment_indicator`

Required summary fields:

- `total_questions_processed`
- `flagged_high_risk_or_inconsistent_responses`
- `overall_completion_status`

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features/tender_response/test_response_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/schemas backend/tests/features/tender_response/test_response_schemas.py
git commit -m "feat: add tender response schemas"
```

## Task 2: Add Tender CSV Parser

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/parsers/tender_csv_parser.py`
- Create: `backend/app/features/tender_response/domain/question_extraction.py`
- Test: `backend/tests/features/tender_response/test_tender_csv_parser.py`

**Step 1: Write the failing test**

Add tests for:

- extracting all questions from a CSV
- supporting mixed domains when present
- not enforcing a fixed number of questions

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features/tender_response/test_tender_csv_parser.py -v`
Expected: FAIL because parser modules do not exist.

**Step 3: Write minimal implementation**

Implement CSV parsing and question normalization.

Assume:

- one row maps to one tender question
- the parser only needs to restore question text and optional metadata columns

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features/tender_response/test_tender_csv_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/parsers backend/app/features/tender_response/domain backend/tests/features/tender_response/test_tender_csv_parser.py
git commit -m "feat: add tender csv parser"
```

## Task 3: Add Historical Alignment Repository

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/repositories/qa_alignment_repository.py`
- Test: `backend/tests/features/tender_response/test_qa_alignment_repository.py`

**Step 1: Write the failing test**

Add tests for:

- no-match retrieval path
- successful historical match retrieval
- threshold handling

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features/tender_response/test_qa_alignment_repository.py -v`
Expected: FAIL because the repository does not exist.

**Step 3: Write minimal implementation**

Implement a repository that:

- embeds the incoming question
- searches `qa_records`
- returns a structured alignment result

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features/tender_response/test_qa_alignment_repository.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/repositories backend/tests/features/tender_response/test_qa_alignment_repository.py
git commit -m "feat: add qa alignment repository"
```

## Task 4: Add Answer Generation and Guardrail Services

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/services/answer_generation_service.py`
- Create: `backend/app/features/tender_response/infrastructure/services/domain_tagging_service.py`
- Create: `backend/app/features/tender_response/infrastructure/services/confidence_service.py`
- Create: `backend/app/features/tender_response/domain/risk_rules.py`
- Test: `backend/tests/features/tender_response/test_answer_generation_service.py`
- Test: `backend/tests/features/tender_response/test_risk_rules.py`

**Step 1: Write the failing test**

Add tests for:

- aligned answer path
- no-match conservative answer path
- unsupported-certification wording flagged as high risk
- inconsistent response flagged without aborting

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features/tender_response/test_answer_generation_service.py backend/tests/features/tender_response/test_risk_rules.py -v`
Expected: FAIL because services do not exist.

**Step 3: Write minimal implementation**

Implement:

- answer generation with and without historical context
- deterministic post-generation guardrail checks
- domain tagging and confidence derivation

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features/tender_response/test_answer_generation_service.py backend/tests/features/tender_response/test_risk_rules.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/services backend/app/features/tender_response/domain/risk_rules.py backend/tests/features/tender_response/test_answer_generation_service.py backend/tests/features/tender_response/test_risk_rules.py
git commit -m "feat: add tender answer generation services"
```

## Task 5: Build the LangGraph Workflow

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/workflows/tender_response_graph.py`
- Test: `backend/tests/features/tender_response/test_tender_response_graph.py`

**Step 1: Write the failing test**

Add tests for:

- dynamic fan-out over arbitrary question counts
- conditional branching for historical match vs no match
- one-question failure not aborting the batch
- final summary reduction

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/features/tender_response/test_tender_response_graph.py -v`
Expected: FAIL because the graph does not exist.

**Step 3: Write minimal implementation**

Implement a `StateGraph` using:

- typed state
- reducers for accumulating question results
- `Send` for per-question fan-out
- conditional edges for alignment branching
- checkpointer for thread-level session memory

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/features/tender_response/test_tender_response_graph.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/workflows backend/tests/features/tender_response/test_tender_response_graph.py
git commit -m "feat: add tender response langgraph workflow"
```

## Task 6: Add Application Use Case and API Route

**Files:**
- Create: `backend/app/features/tender_response/application/process_tender_csv_use_case.py`
- Create: `backend/app/features/tender_response/api/dependencies.py`
- Create: `backend/app/features/tender_response/api/routes.py`
- Modify: `backend/app/bootstrap/routers.py`
- Test: `backend/tests/api/routes/test_tender_response_route.py`
- Test: `backend/tests/features/tender_response/test_process_tender_csv_use_case.py`

**Step 1: Write the failing test**

Add tests for:

- CSV upload accepted at `POST /api/tender/respond`
- JSON response includes per-question results and summary
- invalid file type rejected cleanly

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/routes/test_tender_response_route.py backend/tests/features/tender_response/test_process_tender_csv_use_case.py -v`
Expected: FAIL because route and use case do not exist.

**Step 3: Write minimal implementation**

Add:

- multipart CSV route
- use case that parses CSV, invokes the graph, and returns JSON
- dependency wiring into bootstrap router registration

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/routes/test_tender_response_route.py backend/tests/features/tender_response/test_process_tender_csv_use_case.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/features/tender_response backend/app/bootstrap/routers.py backend/tests/api/routes/test_tender_response_route.py backend/tests/features/tender_response/test_process_tender_csv_use_case.py
git commit -m "feat: add tender response api"
```

## Task 7: Add Demo Data and End-to-End Verification

**Files:**
- Create: `test_data/input/tender_questionnaire_demo.csv`
- Test: `backend/tests/integration/test_tender_response_route.py`

**Step 1: Write the failing test**

Add an integration test using a realistic tender CSV with mixed domains and strict wording.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/integration/test_tender_response_route.py -v`
Expected: FAIL because the route is not fully wired yet.

**Step 3: Write minimal implementation**

Add sample CSV and finalize any missing integration wiring.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/integration/test_tender_response_route.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add test_data/input/tender_questionnaire_demo.csv backend/tests/integration/test_tender_response_route.py
git commit -m "test: add tender response integration coverage"
```

## Task 8: Final Verification

**Files:**
- Verify the full backend tree

**Step 1: Run focused tests**

```bash
pytest backend/tests/features/tender_response -v
pytest backend/tests/api/routes/test_tender_response_route.py -v
pytest backend/tests/integration/test_tender_response_route.py -v
```

Expected: PASS

**Step 2: Run the full backend suite**

```bash
pytest backend/tests -v
```

Expected: PASS

**Step 3: Manual smoke test**

Run the backend and send a CSV to:

```text
POST /api/tender/respond
```

Confirm:

- every question gets a result object
- one bad question does not stop the file
- summary counts are correct
- no fabricated high-risk claims appear without flags

**Step 4: Commit**

```bash
git add backend test_data
git commit -m "feat: add langgraph tender response workflow"
```

## Sources

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/use-graph-api
- LangGraph memory: https://docs.langchain.com/oss/python/langgraph/add-memory

## Decision Summary

Build this as a **state-driven LangGraph workflow** under a new `tender_response` feature.

Key decisions:

- CSV-only input in this phase
- JSON-only output in this phase
- Graph API over generic agent loop
- per-question fan-out with reducers
- conditional branch for historical match vs no match
- thread-level short-term memory only
- deterministic risk checks after generation
