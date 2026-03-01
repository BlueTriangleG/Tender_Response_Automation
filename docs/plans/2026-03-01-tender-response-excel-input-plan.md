# Tender Response Excel Input Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `.xlsx` support to tender response uploads while keeping Excel preprocessing semantically aligned with the current CSV flow and leaving the LangGraph workflow contract unchanged.

**Architecture:** Keep file-format handling inside the `tender_response` feature boundary. Refactor the current CSV-only parser into a shared tabular normalization path that converts rows from either CSV or Excel into the same `TenderQuestion` objects before workflow execution. The workflow layer should continue consuming normalized questions only and remain ignorant of input format details.

**Tech Stack:** FastAPI, Pydantic, pytest, `openpyxl`, LangGraph.

---

## Recommended Scope

Implement the smallest production-safe version first:

- Support `.csv` and `.xlsx`
- Read only the first visible worksheet for Excel uploads
- Treat the first non-empty row as headers
- Reuse the existing header matching rules in `question_extraction.py`
- Preserve current response contract unless sheet provenance is explicitly needed
- Keep `.xls` out of scope for v1

## Design Decision

Use one shared tabular preprocessing path instead of two separate parsers with duplicated normalization logic.

Recommended shape:

- `CsvTenderInputParser` parses bytes/text into `headers + row dicts`
- `ExcelTenderInputParser` parses workbook bytes into `headers + row dicts`
- `TenderTabularNormalizer` applies the current question/header extraction logic and returns `TenderQuestion`
- `TenderResponseRunner` chooses the parser by file extension, then passes normalized questions into the existing workflow state

This keeps CSV and Excel behavior aligned by construction.

## Task 1: Lock the Shared Preprocessing Contract with Tests

**Files:**
- Create: `backend/tests/features/tender_response/test_tender_tabular_normalizer.py`
- Modify: `backend/tests/features/tender_response/test_tender_csv_parser.py`
- Modify: `backend/tests/features/tender_response/test_process_tender_csv_use_case.py`

**Step 1: Write the failing normalizer tests**

Add tests that define the shared behavior for tabular inputs:

- question column detection still uses the current aliases
- blank question rows are skipped
- missing question ids still become `row-{n}`
- declared domain remains optional
- row order and `source_row_index` stay stable

Example test shape:

```python
def test_normalizer_extracts_questions_from_tabular_rows() -> None:
    normalizer = TenderTabularNormalizer()

    result = normalizer.normalize_rows(
        headers=["question_id", "domain", "question"],
        rows=[
            {"question_id": "q-1", "domain": "Security", "question": "TLS?"},
            {"question_id": "", "domain": "", "question": "SSO?"},
        ],
        source_file_name="tender.xlsx",
    )

    assert [item.question_id for item in result.questions] == ["q-1", "row-2"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_tender_tabular_normalizer.py -v
```

Expected: FAIL because `TenderTabularNormalizer` does not exist yet.

**Step 3: Tighten runner-level expectations**

Update the existing runner/use-case tests so they describe the desired future behavior:

- `.csv` still works unchanged
- `.xlsx` is accepted
- unsupported extensions still fail with a clear validation error

Keep these tests focused on upload validation and parser dispatch, not workflow internals.

**Step 4: Run the focused runner tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_process_tender_csv_use_case.py -v
```

Expected: FAIL on the new `.xlsx` acceptance case.

**Step 5: Commit**

```bash
git add backend/tests/features/tender_response/test_tender_tabular_normalizer.py backend/tests/features/tender_response/test_tender_csv_parser.py backend/tests/features/tender_response/test_process_tender_csv_use_case.py
git commit -m "test: define shared tender tabular preprocessing contract"
```

## Task 2: Introduce a Shared Tabular Normalizer

**Files:**
- Create: `backend/app/features/tender_response/infrastructure/parsers/tender_tabular_normalizer.py`
- Modify: `backend/app/features/tender_response/domain/models.py`
- Modify: `backend/app/features/tender_response/domain/question_extraction.py`
- Test: `backend/tests/features/tender_response/test_tender_tabular_normalizer.py`

**Step 1: Write the minimal implementation**

Create a normalizer that accepts:

- `headers: list[str]`
- `rows: list[dict[str, str]]`
- `source_file_name: str`

and returns the same parse result shape currently used by CSV parsing.

Suggested implementation outline:

```python
class TenderTabularNormalizer:
    def normalize_rows(self, *, headers, rows, source_file_name):
        question_column = find_first_matching_column(headers, QUESTION_COLUMN_CANDIDATES)
        if question_column is None:
            raise ValueError("Input must include a question column.")
        ...
```

**Step 2: Rename CSV-shaped domain vocabulary if needed**

If it improves clarity without causing unnecessary churn, rename:

- `TenderCsvParseResult` -> `TenderInputParseResult`

If that rename touches too many files for too little value, keep the existing type for v1 and document the mismatch as technical debt.

**Step 3: Keep header semantics identical**

Do not add Excel-only header rules. Reuse:

- `QUESTION_COLUMN_CANDIDATES`
- `QUESTION_ID_COLUMN_CANDIDATES`
- `DOMAIN_COLUMN_CANDIDATES`

from `question_extraction.py` so CSV and Excel behave the same.

**Step 4: Run tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_tender_tabular_normalizer.py tests/features/tender_response/test_tender_csv_parser.py -v
```

Expected: PASS for shared normalization tests, existing CSV semantics preserved.

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/parsers/tender_tabular_normalizer.py backend/app/features/tender_response/domain/models.py backend/app/features/tender_response/domain/question_extraction.py backend/tests/features/tender_response/test_tender_tabular_normalizer.py backend/tests/features/tender_response/test_tender_csv_parser.py
git commit -m "refactor: extract shared tender tabular normalizer"
```

## Task 3: Refactor CSV Parsing to Use the Shared Normalizer

**Files:**
- Modify: `backend/app/features/tender_response/infrastructure/parsers/tender_csv_parser.py`
- Test: `backend/tests/features/tender_response/test_tender_csv_parser.py`

**Step 1: Change the CSV parser responsibility**

Make `TenderCsvParser` responsible only for:

- decoding CSV text into headers + row dictionaries
- delegating normalization to `TenderTabularNormalizer`

Suggested shape:

```python
class TenderCsvParser:
    def __init__(self, normalizer: TenderTabularNormalizer | None = None) -> None:
        self._normalizer = normalizer or TenderTabularNormalizer()
```

**Step 2: Preserve current behavior**

Keep these semantics unchanged:

- `csv.DictReader`
- skipped blank question rows
- fallback row ids
- same error when no question column exists

**Step 3: Run tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_tender_csv_parser.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/app/features/tender_response/infrastructure/parsers/tender_csv_parser.py backend/tests/features/tender_response/test_tender_csv_parser.py
git commit -m "refactor: route csv parsing through shared tender normalizer"
```

## Task 4: Add Excel Parsing with CSV-Aligned Semantics

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/features/tender_response/infrastructure/parsers/tender_excel_parser.py`
- Create: `backend/tests/features/tender_response/test_tender_excel_parser.py`

**Step 1: Write the failing Excel parser tests**

Cover the minimum supported workbook behavior:

- first visible sheet is used
- first row becomes headers
- rows become dictionaries keyed by header text
- empty question rows are skipped after shared normalization
- missing question column raises the same validation error as CSV

Use an in-memory workbook in tests.

Example shape:

```python
def test_tender_excel_parser_extracts_questions_from_first_sheet() -> None:
    workbook_bytes = build_workbook_bytes(
        [
            ["question_id", "domain", "question"],
            ["q-1", "Security", "TLS?"],
        ]
    )
    parser = TenderExcelParser()
    result = parser.parse_bytes(workbook_bytes, source_file_name="tender.xlsx")
    assert result.questions[0].question_id == "q-1"
```

**Step 2: Add the dependency**

Add `openpyxl` to `backend/pyproject.toml`.

**Step 3: Implement the minimal parser**

`TenderExcelParser` should:

- accept raw bytes
- open the workbook in read-only/data-only mode
- choose the first visible sheet
- convert rows to strings
- normalize blank cells to `""`
- delegate to `TenderTabularNormalizer`

Do not support:

- multiple-sheet merging
- formulas requiring recalculation
- `.xls`

**Step 4: Run tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_tender_excel_parser.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/features/tender_response/infrastructure/parsers/tender_excel_parser.py backend/tests/features/tender_response/test_tender_excel_parser.py
git commit -m "feat: add xlsx parser for tender response uploads"
```

## Task 5: Refactor the Runner to Dispatch by File Type

**Files:**
- Modify: `backend/app/features/tender_response/application/tender_response_runner.py`
- Create: `backend/app/features/tender_response/infrastructure/parsers/base.py`
- Test: `backend/tests/features/tender_response/test_process_tender_csv_use_case.py`

**Step 1: Write the failing parser-dispatch tests**

Define runner behavior for:

- `.csv` -> CSV parser
- `.xlsx` -> Excel parser
- unsupported extension -> `ValueError`

If useful, inject fake parsers into the runner so dispatch can be tested without real parsing.

**Step 2: Introduce a parser protocol or registry**

Recommended shape:

```python
class TenderInputParser(Protocol):
    supported_extensions: tuple[str, ...]
    async def parse_upload(self, upload_file: UploadFile): ...
```

or a simpler sync interface that the runner wraps after reading bytes.

**Step 3: Remove CSV-only assumptions from the runner**

The runner should stop doing:

- hard `.csv` suffix rejection
- unconditional UTF-8 decode before parser selection

Instead:

- inspect extension
- read bytes once
- route bytes to the chosen parser

**Step 4: Keep workflow seeding unchanged**

Do not change `_build_initial_state` or workflow registry behavior unless a test proves it is necessary.

**Step 5: Run tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response/test_process_tender_csv_use_case.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS on `.csv`; new `.xlsx` case still fails until route tests are updated if they assert CSV-only wording.

**Step 6: Commit**

```bash
git add backend/app/features/tender_response/application/tender_response_runner.py backend/app/features/tender_response/infrastructure/parsers/base.py backend/tests/features/tender_response/test_process_tender_csv_use_case.py
git commit -m "refactor: dispatch tender upload parsing by file extension"
```

## Task 6: Update API Route Tests and Validation Messaging

**Files:**
- Modify: `backend/app/features/tender_response/api/routes.py`
- Modify: `backend/tests/api/routes/test_tender_response_route.py`
- Modify: `README.md`

**Step 1: Update route tests**

Replace the current “reject all non-CSV uploads” expectation with:

- accept `.xlsx`
- reject unsupported types with wording like `Only CSV and XLSX files are supported`

**Step 2: Keep route thin**

Do not move file-type logic into the route unless required for transport-level validation. The runner should remain the main validation seam.

**Step 3: Adjust docs**

Update README tender response wording so it no longer claims CSV-only behavior.

**Step 4: Run tests**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/api/routes/test_tender_response_route.py tests/bootstrap/test_routers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/features/tender_response/api/routes.py backend/tests/api/routes/test_tender_response_route.py README.md
git commit -m "docs: align tender response route with csv and xlsx support"
```

## Task 7: Add an End-to-End XLSX Integration Test

**Files:**
- Modify: `backend/tests/integration/test_tender_response_route_integration.py`
- Optional reference: `test_data/input/tender_questionnaire_sample.xlsx`

**Step 1: Add an integration test for `.xlsx` upload**

Reuse the fake workflow services already used by the integration suite. The new test should confirm:

- uploaded `.xlsx` reaches the same workflow
- normalized questions count matches expectation
- response schema is unchanged

Prefer generating workbook bytes inside the test instead of relying on fixture files unless the fixture materially improves readability.

**Step 2: Run the integration test**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS for both CSV and XLSX paths.

**Step 3: Commit**

```bash
git add backend/tests/integration/test_tender_response_route_integration.py
git commit -m "test: cover xlsx tender response upload end to end"
```

## Task 8: Verify the Full Backend Slice

**Files:**
- No code changes

**Step 1: Run the tender-response test slice**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/features/tender_response tests/api/routes/test_tender_response_route.py tests/integration/test_tender_response_route_integration.py -v
```

Expected: PASS.

**Step 2: Run static checks**

Run:

```bash
cd backend
../backend/.venv/bin/ruff check app tests
../backend/.venv/bin/mypy app
```

Expected: PASS.

**Step 3: Run a quick regression on startup wiring**

Run:

```bash
cd backend
../backend/.venv/bin/pytest tests/bootstrap/test_routers.py tests/features/tender_response/test_tender_response_modules.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add .
git commit -m "chore: verify tender response excel upload support"
```

## Task 9: Optional Frontend Follow-Up

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/api.test.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Remove the frontend `.csv` guard**

Change `processTenderWorkbook` so it accepts `.xlsx` alongside `.csv`.

**Step 2: Update UI copy**

Replace phrases like `Select a tender csv` with `Select a tender CSV or XLSX file`.

**Step 3: Run frontend tests**

Run:

```bash
cd frontend
npm test -- --runInBand
```

Expected: PASS.

**Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts frontend/src/App.tsx
git commit -m "feat: allow xlsx tender uploads in frontend"
```

## Notes for the Implementer

- Do not refactor workflow nodes unless tests prove it is required.
- Do not add `.xls` support in the same change.
- Do not create Excel-specific header alias rules.
- If sheet provenance becomes important later, extend `QuestionMetadata` in `schemas/responses.py` with `source_sheet_name`; do not guess now.
- Prefer generated workbook bytes in tests over binary fixtures to keep diffs reviewable.
