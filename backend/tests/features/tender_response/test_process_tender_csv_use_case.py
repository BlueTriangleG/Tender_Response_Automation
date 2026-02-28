from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.features.tender_response.application.process_tender_csv_use_case import (
    ProcessTenderCsvUseCase,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
)


def make_upload_file(
    filename: str,
    content: bytes,
    content_type: str,
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class FakeWorkflow:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.configs: list[dict] = []

    async def ainvoke(self, state: dict, config: dict) -> dict:
        self.calls.append(state)
        self.configs.append(config)
        return {
            "question_results": [
                TenderQuestionResponse(
                    question_id="q-001",
                    original_question="Do you support TLS 1.2 or above?",
                    generated_answer="Yes.",
                    domain_tag="security",
                    confidence_level="high",
                    confidence_reason="Direct historical evidence supports the answer.",
                    historical_alignment_indicator=True,
                    status="completed",
                    grounding_status="grounded",
                    flags=QuestionFlags(high_risk=False, inconsistent_response=False),
                    risk=QuestionRisk(
                        level="medium",
                        reason="Security posture responses should still be reviewed.",
                    ),
                    metadata=QuestionMetadata(
                        source_row_index=0,
                        alignment_record_id="qa-1",
                        alignment_score=0.92,
                    ),
                    references=[
                        QuestionReference(
                            alignment_record_id="qa-1",
                            alignment_score=0.92,
                            source_doc="history.csv",
                            matched_question="Historical TLS question",
                            matched_answer="Yes.",
                            used_for_answer=True,
                        )
                    ],
                    error_message=None,
                    extensions={},
                )
            ],
            "summary": TenderResponseSummary(
                total_questions_processed=1,
                flagged_high_risk_or_inconsistent_responses=0,
                overall_completion_status="completed",
                completed_questions=1,
                unanswered_questions=0,
                failed_questions=0,
            ),
        }


async def test_process_upload_parses_csv_and_invokes_workflow() -> None:
    workflow = FakeWorkflow()
    use_case = ProcessTenderCsvUseCase(workflow=workflow)

    result = await use_case.process_upload(
        make_upload_file(
            "tender.csv",
            b"question_id,question\nq-001,\"Do you support TLS 1.2 or above?\"\n",
            "text/csv",
        ),
        TenderResponseRequestOptions(session_id="session-123", alignment_threshold=0.84),
    )

    assert result.source_file_name == "tender.csv"
    assert result.total_questions_processed == 1
    assert result.questions[0].generated_answer == "Yes."
    assert workflow.calls[0]["questions"][0].question_id == "q-001"
    assert workflow.calls[0]["request_id"] == result.request_id
    assert workflow.configs[0] == {"configurable": {"thread_id": result.request_id}}


async def test_process_upload_rejects_non_csv_files() -> None:
    use_case = ProcessTenderCsvUseCase(workflow=FakeWorkflow())

    try:
        await use_case.process_upload(
            make_upload_file("tender.md", b"# nope", "text/markdown"),
            TenderResponseRequestOptions(session_id="session-123"),
        )
    except ValueError as exc:
        assert "csv" in str(exc).lower()
    else:
        raise AssertionError("Expected use case to reject non-CSV files")
