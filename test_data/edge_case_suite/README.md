# Edge-Case Dataset Suite

This suite extends the existing demo data with regression-oriented assets for the current backend contract:

- Historical repository ingest uses CSV
- Tender inference input uses CSV and XLSX
- Output expectations are captured as oracle JSON

The goal is to cover realistic edge cases around:

- CSV header normalization and alias handling
- Ambiguous or invalid ingest files
- Duplicate and conflicting historical records
- Retrieval outcomes: grounded, no reference, insufficient reference
- Safety-sensitive wording around certifications and pricing
- Workflow outcomes: completed, unanswered, zero-question batches

## Structure

```text
edge_case_suite/
  historical_repository/
  input/
  expected_output/
  manifest.yaml
  README.md
```

## Historical Repository Files

### `historical_repository/01_clean_security_architecture.csv`

Tests the happy path for ingest with standard `question,answer,domain` headers. Use this as the baseline history file for exact-match and paraphrase retrieval.

### `historical_repository/02_header_aliases.csv`

Tests ingest through header aliases such as `Question Text`, `Approved Answer`, and `Practice Area`. Also expands coverage for AI citations, data privacy, penetration testing, and deployment model wording.

### `historical_repository/03_ambiguous_headers.csv`

Intentional negative ingest case. It includes both `question` and `customer_question`, which should force the header matcher into ambiguity and exercise the LLM fallback or failure path.

### `historical_repository/04_duplicates_and_conflicts_a.csv`

Introduces approved commercial and compliance positions that can later be paired with conflict files. Useful for testing duplicate detection, conflicting pricing language, and standard audit-log retention.

### `historical_repository/05_duplicates_and_conflicts_b.csv`

Pairs with file 04. Contains one exact duplicate row plus more restrictive alternative answers for the same topics. This is designed to expose the current exact-content dedupe behavior and conflict handling gaps.

### `historical_repository/06_dirty_rows_and_quoting.csv`

Covers blank required fields, extra whitespace around domains, comma-heavy answers, and multiline quoted CSV cells. Use this to test parser robustness and row-level normalization failures.

## Tender Input Files

### `input/01_exact_and_paraphrase.csv`

Happy-path inference set. Questions should align to clean historical answers through either exact wording or close paraphrase.

### `input/02_no_reference_vs_insufficient.csv`

Designed to separate true misses from near-matches that still lack enough evidence. Useful for validating `no_reference` versus `insufficient_reference`.

### `input/03_risk_and_contradictions.csv`

Exercises unsafe certification wording, adversarial contradiction prompts, and commercial over-commitment requests. This is the main safety-oriented tender input file.

### `input/04_mixed_batch_12_questions.csv`

A realistic mixed-domain batch with exact matches, paraphrases, no-reference questions, and safety-sensitive commercial/compliance wording. Use this for end-to-end workflow demos and summary behavior checks.

### `input/05_header_aliases_and_blank_rows.csv`

Uses alias headers such as `Question Text`, `Category`, and `ID`, while also including blank rows and a missing ID. It validates parser normalization and auto-generated row IDs.

### `input/06_blank_rows_only.csv`

Intentional zero-question batch. Every row has a blank question value, so parsing should produce no questions and the workflow should terminate cleanly with a zero-count summary.

### `input/07_exact_and_paraphrase.xlsx`

Workbook version of the happy-path exact/paraphrase case. Use this to confirm XLSX uploads receive the same preprocessing and grounding behavior as the equivalent CSV path.

## Oracle Files

Oracle JSON files in `expected_output/` are not literal backend responses. They describe the expected behavioral outcome for each tender file:

- expected summary shape
- allowed workflow statuses
- grounded versus unanswered intent
- whether the answer should be null
- required or forbidden phrases

This keeps the dataset useful for LLM-based workflows where exact prose may vary.

## Recommended Pairings

- `01_exact_and_paraphrase.csv`
  - ingest `01_clean_security_architecture.csv`
  - ingest `02_header_aliases.csv`
- `02_no_reference_vs_insufficient.csv`
  - ingest `01_clean_security_architecture.csv`
  - ingest `02_header_aliases.csv`
  - optionally ingest `06_dirty_rows_and_quoting.csv`
- `03_risk_and_contradictions.csv`
  - ingest `01_clean_security_architecture.csv`
  - ingest `02_header_aliases.csv`
  - ingest `04_duplicates_and_conflicts_a.csv`
  - ingest `05_duplicates_and_conflicts_b.csv`
- `04_mixed_batch_12_questions.csv`
  - ingest all historical files except the intentionally invalid `03_ambiguous_headers.csv`
- `05_header_aliases_and_blank_rows.csv`
  - ingest `01_clean_security_architecture.csv`
  - ingest `02_header_aliases.csv`
- `06_blank_rows_only.csv`
  - any baseline history set is fine; the point is parser behavior
- `07_exact_and_paraphrase.xlsx`
  - ingest `01_clean_security_architecture.csv`
  - ingest `02_header_aliases.csv`

## Notes

- The current backend only persists CSV history files, even though the older demo pack includes Markdown, TXT, JSON, and XLSX artifacts.
- Exact-content duplicate history rows collapse to the same record ID even across different files.
- Safety-sensitive questions about certifications and pricing should be evaluated conservatively; these datasets are designed to surface over-claiming risks.

## Live E2E Command

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/e2e/live -m live_e2e -v
```

The live E2E fixtures load `OPENAI_API_KEY` from `backend/.env` automatically, with an exported shell variable still taking precedence.

Artifacts from live runs are written under `backend/.artifacts/edge_case_suite/`.
