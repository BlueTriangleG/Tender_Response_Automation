# Edge-Case Dataset Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a comprehensive regression-oriented dataset suite that exercises realistic CSV ingest, retrieval, grounding, risk, contradiction, and workflow-summary edge cases for the current backend.

**Architecture:** Keep the existing `test_data/` demo pack intact and add a separate `edge_case_suite/` subtree. Split assets into historical ingest inputs, tender inference inputs, oracle JSON files, and a manifest/README so each file has a clear testing purpose and can be consumed manually or by future automation.

**Tech Stack:** CSV, JSON, Markdown documentation, repository-local test data conventions

---

### Task 1: Define dataset layout and coverage

**Files:**
- Create: `test_data/edge_case_suite/README.md`
- Create: `test_data/edge_case_suite/manifest.yaml`
- Reference: `test_data/README.md`

**Step 1: Enumerate the core system behaviors to cover**

- History ingest header alias detection
- History ingest ambiguous/missing headers
- History ingest duplicate and conflicting records
- History ingest blank rows and quoted multiline answers
- Tender parsing with aliases, missing IDs, blank rows
- Retrieval outcomes: grounded, no reference, insufficient reference
- Post-generation outcomes: completed, unanswered, failed
- Batch summary precedence and flagged results

**Step 2: Define a directory structure that separates positive and negative cases**

```text
test_data/edge_case_suite/
  historical_repository/
  input/
  expected_output/
  README.md
  manifest.yaml
```

**Step 3: Save the file-level purpose in README and machine-readable metadata in manifest**

Expected: every dataset file appears in both places with a short “tests what” description.

### Task 2: Create historical CSV inputs

**Files:**
- Create: `test_data/edge_case_suite/historical_repository/01_clean_security_architecture.csv`
- Create: `test_data/edge_case_suite/historical_repository/02_header_aliases.csv`
- Create: `test_data/edge_case_suite/historical_repository/03_ambiguous_headers.csv`
- Create: `test_data/edge_case_suite/historical_repository/04_duplicates_and_conflicts_a.csv`
- Create: `test_data/edge_case_suite/historical_repository/05_duplicates_and_conflicts_b.csv`
- Create: `test_data/edge_case_suite/historical_repository/06_dirty_rows_and_quoting.csv`

**Step 1: Build one clean ingest file**

Include standard `question,answer,domain` headers with realistic Security, Architecture, Infrastructure, AI, Compliance, and Pricing content.

**Step 2: Build one alias-header ingest file**

Use headers like `Question Text`, `Approved Answer`, and `Practice Area`.

**Step 3: Build negative ingest files**

- One file with ambiguous question headers
- One pair of files that duplicate and conflict on certain commercial/compliance claims
- One file with blank fields, quoted commas, and multiline answers

**Step 4: Ensure all examples reflect current product positioning**

Avoid fake certifications unless the file is intentionally testing unsafe claims.

### Task 3: Create tender CSV inputs and oracle JSON files

**Files:**
- Create: `test_data/edge_case_suite/input/01_exact_and_paraphrase.csv`
- Create: `test_data/edge_case_suite/input/02_no_reference_vs_insufficient.csv`
- Create: `test_data/edge_case_suite/input/03_risk_and_contradictions.csv`
- Create: `test_data/edge_case_suite/input/04_mixed_batch_12_questions.csv`
- Create: `test_data/edge_case_suite/input/05_header_aliases_and_blank_rows.csv`
- Create: `test_data/edge_case_suite/input/06_blank_rows_only.csv`
- Create: matching `test_data/edge_case_suite/expected_output/*.oracle.json`

**Step 1: For each tender CSV, focus on one or two core behaviors**

Examples:
- exact match vs paraphrase
- no reference vs insufficient reference
- unsupported certification wording
- mixed batch summary precedence
- parser alias handling and blank-row skipping
- empty effective batch

**Step 2: Write oracle JSON as behavioral expectations, not exact LLM prose**

Use fields like:

```json
{
  "expected_status": "unanswered",
  "expected_grounding_status": "insufficient_reference",
  "generated_answer_should_be_null": true
}
```

**Step 3: Include summary-level expectations**

Capture `total_questions_processed`, expected counts of `completed`, `unanswered`, `failed`, and target overall completion status.

### Task 4: Validate the dataset assets

**Files:**
- Validate: `test_data/edge_case_suite/**/*.csv`
- Validate: `test_data/edge_case_suite/**/*.json`

**Step 1: Run JSON parsing over every oracle**

Run: `python - <<'PY' ... json.load(...)`
Expected: all oracle files parse successfully

**Step 2: Run CSV header/row sanity checks**

Run: `python - <<'PY' ... csv.DictReader(...)`
Expected: each CSV file has readable headers and row counts

**Step 3: Report the final dataset inventory**

List all created files and summarize what each group covers.
