from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.features.tender_response.api.dependencies import get_process_tender_csv_use_case
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    TenderQuestionResponse,
    TenderResponseSummary,
    TenderResponseWorkflowResponse,
)
from app.main import app


def test_tender_response_route_accepts_csv_upload_and_returns_json() -> None:
    client = TestClient(app)
    mock_use_case = MagicMock()
    mock_use_case.process_upload = AsyncMock(
        return_value=TenderResponseWorkflowResponse(
            request_id="req-123",
            session_id="session-123",
            source_file_name="tender.csv",
            total_questions_processed=1,
            questions=[
                TenderQuestionResponse(
                    question_id="q-001",
                    original_question="Do you support TLS 1.2 or above?",
                    generated_answer="Yes.",
                    domain_tag="security",
                    confidence_level="high",
                    historical_alignment_indicator=True,
                    status="completed",
                    flags=QuestionFlags(high_risk=False, inconsistent_response=False),
                    metadata=QuestionMetadata(
                        source_row_index=0,
                        alignment_record_id="qa-1",
                        alignment_score=0.92,
                    ),
                    error_message=None,
                    extensions={},
                )
            ],
            summary=TenderResponseSummary(
                total_questions_processed=1,
                flagged_high_risk_or_inconsistent_responses=0,
                overall_completion_status="completed",
                completed_questions=1,
                failed_questions=0,
            ),
        )
    )

    app.dependency_overrides[get_process_tender_csv_use_case] = lambda: mock_use_case
    try:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    "tender.csv",
                    b'question_id,question\nq-001,"Do you support TLS 1.2 or above?"\n',
                    "text/csv",
                )
            },
            data={"sessionId": "session-123", "alignmentThreshold": "0.84"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_questions_processed"] == 1
    assert payload["questions"][0]["generated_answer"] == "Yes."
    assert payload["summary"]["overall_completion_status"] == "completed"


def test_tender_response_route_rejects_non_csv_upload() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/tender/respond",
        files={"file": ("tender.md", b"# nope", "text/markdown")},
    )

    assert response.status_code == 400
