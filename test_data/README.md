# Tender Test Dataset

This dataset is designed for the Pan Software multi-agent tender response use case.
It gives you a realistic local demo pack with:

- A mixed-format historical tender repository
- A new tender questionnaire in both CSV and Excel formats
- An example expected output JSON aligned with the current frontend result shape

## Contents

- `historical_repository/`
  - Mixed Markdown, TXT, and JSON prior tender responses used as document-evidence ingest inputs
  - Includes overlapping answers, tone variations, and one deliberate commercial conflict
  - Also includes `historical_repository_qa.csv` and `historical_repository_qa.xlsx`, flat question-answer-domain repositories for simple QA-table ingestion flows
  - Includes `operations_playbook.txt` as a plain-text document-ingest sample for manual smoke testing
- `edge_case_suite/`
  - A regression-oriented CSV/JSON suite for the current backend contract
  - Includes ingest negatives, retrieval edge cases, safety-sensitive tender wording, and oracle files
- `input/tender_questionnaire_sample.csv`
  - Human-readable source version of the sample questionnaire
- `input/tender_questionnaire_sample.xlsx`
  - Excel file for upload and processing demos
- `expected_output/tender_response_expected.json`
  - Example structured output with alignment, confidence, risk, and summary fields

## Scenario Coverage

The dataset covers these domains:

- Architecture
- Security
- Infrastructure
- AI
- Compliance
- Pricing

It intentionally includes:

- Strong historical matches for encryption, SSO, audit logging, data residency, and AI governance
- A deliberate pair of contradictory SSL positioning records plus matching tender questions to demo session conflict detection
- A partial-match deployment question that should be answered carefully
- A pricing question with conflicting historical assumptions
- A certification question that must not be answered with an unsupported claim

## Recommended Demo Flow

1. Load the tabular QA files in `historical_repository/` into `qa_records`.
2. Load the non-tabular history files in `historical_repository/` into `document_records`.
3. Upload `input/tender_questionnaire_sample.xlsx`.
4. Run the LangGraph workflow per question.
5. Compare generated output with `expected_output/tender_response_expected.json`.

## Regression-Oriented Suite

If you want coverage instead of just a single demo path, use `edge_case_suite/`.

- `edge_case_suite/historical_repository/`
  - CSV-only historical ingest cases aligned to the current backend
- `edge_case_suite/input/`
  - Tender CSV files that isolate exact-match, paraphrase, no-reference, insufficient-reference, and safety-sensitive scenarios
- `edge_case_suite/expected_output/`
  - Oracle JSON files describing expected workflow behavior without overfitting to exact LLM wording
- `edge_case_suite/manifest.yaml`
  - Machine-readable mapping between inputs, history files, and intended coverage

## Assumptions

- Historical answers represent approved prior positioning, not guaranteed product truth.
- Unsupported certifications should be flagged for human review rather than invented.
- Pricing answers must stay conservative when historical commercial assumptions conflict.
