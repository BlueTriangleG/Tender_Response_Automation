# API Calls And Sample Payloads

This document shows the current API surface in the most practical way possible: what to call, what to send, and what comes back.

Base URL:

```text
http://127.0.0.1:8000
```

Before calling the LLM-backed endpoints:

1. Copy [backend/.env.example](/Users/autumn/Learning/interview%20questions/pans_software/backend/.env.example) to `backend/.env`
2. Set:

```text
OPENAI_API_KEY=your_key_here
```

## Endpoints

- `GET /api/health`
- `POST /api/ingest/history`
- `POST /api/tender/respond`

## 1. Health Check

### curl

```bash
curl -sS http://127.0.0.1:8000/api/health
```

### Postman

- Method: `GET`
- URL: `http://127.0.0.1:8000/api/health`

## 2. Ingest Historical Repository

Use this endpoint to upload historical tender materials before generating responses.

Supported demo inputs include:

- CSV
- XLSX
- Markdown
- TXT
- JSON

Useful sample files:

- [historical_repository_qa.csv](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository/historical_repository_qa.csv)
- [historical_repository_qa.xlsx](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository/historical_repository_qa.xlsx)
- [security_platform_overview.md](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository/security_platform_overview.md)
- [operations_playbook.txt](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository/operations_playbook.txt)

### curl

```bash
curl -sS -X POST http://127.0.0.1:8000/api/ingest/history \
  -F "files=@test_data/historical_repository/historical_repository_qa.csv" \
  -F "files=@test_data/historical_repository/security_platform_overview.md" \
  -F "files=@test_data/historical_repository/operations_playbook.txt" \
  -F "outputFormat=json" \
  -F "similarityThreshold=0.72"
```

### Postman

- Method: `POST`
- URL: `http://127.0.0.1:8000/api/ingest/history`
- Body type: `form-data`
- Fields:
  - `files` as `File` and add one or more files
  - `outputFormat` as `Text`, example: `json`
  - `similarityThreshold` as `Text`, example: `0.72`

### Sample Response Shape

```json
{
  "request_id": "9d5592f5-427f-4ee2-92f1-728e8caad8bb",
  "total_file_count": 3,
  "processed_file_count": 3,
  "failed_file_count": 0,
  "request_options": {
    "output_format": "json",
    "similarity_threshold": 0.72
  },
  "files": [
    {
      "status": "processed",
      "payload": {
        "file_name": "historical_repository_qa.csv",
        "extension": ".csv",
        "parsed_kind": "tabular"
      },
      "ingested_row_count": 12,
      "storage_target": "qa_records"
    }
  ]
}
```

## 3. Generate Tender Responses

Upload the new tender questionnaire after ingesting the historical repository.

Useful sample files:

- [tender_questionnaire_sample.xlsx](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.xlsx)
- [tender_questionnaire_sample.csv](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.csv)

### curl

```bash
curl -sS -X POST http://127.0.0.1:8000/api/tender/respond \
  -F "file=@test_data/input/tender_questionnaire_sample.xlsx" \
  -F "sessionId=demo-session-001" \
  -F "alignmentThreshold=0.5"
```

### Postman

- Method: `POST`
- URL: `http://127.0.0.1:8000/api/tender/respond`
- Body type: `form-data`
- Fields:
  - `file` as `File`
  - `sessionId` as `Text`, optional, example: `demo-session-001`
  - `alignmentThreshold` as `Text`, optional, example: `0.5`

### Sample Request Payload Semantics

- `file`
  - required
  - tender questionnaire in `.xlsx` or `.csv`
- `sessionId`
  - optional
  - when reused across requests, enables shared session memory and cross-run conflict review
- `alignmentThreshold`
  - optional
  - float between `0.1` and `0.99`

### Sample Response Shape

```json
{
  "request_id": "6bdbe3cb-8bbd-4e0a-bfaf-607ef4a5ec90",
  "session_id": "demo-session-001",
  "source_file_name": "tender_questionnaire_sample.xlsx",
  "total_questions_processed": 14,
  "questions": [
    {
      "question_id": "q-001",
      "original_question": "Does the platform support SAML 2.0 and OpenID Connect for single sign-on?",
      "generated_answer": "Yes. The platform supports both SAML 2.0 and OpenID Connect based single sign-on for enterprise identity integration.",
      "domain_tag": "architecture",
      "confidence_level": "high",
      "confidence_reason": "The retrieved references directly support the answer.",
      "historical_alignment_indicator": true,
      "status": "completed",
      "grounding_status": "grounded",
      "flags": {
        "high_risk": false,
        "inconsistent_response": false,
        "has_conflict": false
      },
      "risk": {
        "level": "low",
        "reason": "The answer is directly supported by historical references."
      },
      "metadata": {
        "source_row_index": 0,
        "alignment_record_id": "record-123",
        "alignment_score": 0.84
      },
      "references": [],
      "error_message": null,
      "extensions": {}
    }
  ],
  "summary": {
    "total_questions_processed": 14,
    "flagged_high_risk_or_inconsistent_responses": 1,
    "overall_completion_status": "completed_with_flags",
    "completed_questions": 12,
    "unanswered_questions": 1,
    "failed_questions": 1,
    "conflict_count": 0
  }
}
```

## Demo Flow

1. Call `POST /api/ingest/history` with files from [test_data/historical_repository](/Users/autumn/Learning/interview%20questions/pans_software/test_data/historical_repository).
2. Call `POST /api/tender/respond` with [tender_questionnaire_sample.xlsx](/Users/autumn/Learning/interview%20questions/pans_software/test_data/input/tender_questionnaire_sample.xlsx).
3. Inspect:
   - answered questions
   - unanswered questions
   - confidence and risk
   - conflict flags
   - batch summary

## Running Live E2E

Live E2E validates the end-to-end workflow against the real OpenAI-backed stack.

Command:

```bash
cd backend
UV_CACHE_DIR=/tmp/pans-software-uv-cache uv run pytest tests/e2e/live -m live_e2e -v
```

Requirements:

- valid `OPENAI_API_KEY`
- backend dependencies synced with `uv`
- test data available under [test_data/edge_case_suite](/Users/autumn/Learning/interview%20questions/pans_software/test_data/edge_case_suite)

## Recommended Postman Collection Layout

If you create a Postman collection, use these requests:

- `Health`
- `Ingest Historical Repository`
- `Tender Respond`

Recommended environment variables:

- `baseUrl = http://127.0.0.1:8000`
- `sessionId = demo-session-001`
