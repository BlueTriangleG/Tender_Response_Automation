from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    TenderQuestionResponse,
    TenderResponseSummary,
    TenderResponseWorkflowResponse,
)


def test_tender_question_response_contains_required_business_fields() -> None:
    response = TenderQuestionResponse(
        question_id="q-001",
        original_question="Do you support TLS 1.2 or above?",
        generated_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
        domain_tag="security",
        confidence_level="high",
        historical_alignment_indicator=True,
        status="completed",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        metadata=QuestionMetadata(
            source_row_index=0,
            alignment_record_id="qa_123",
            alignment_score=0.92,
        ),
        reference=QuestionReference(
            alignment_record_id="qa_123",
            alignment_score=0.92,
            source_doc="historical_repository_qa.csv",
            matched_question="Do you support TLS 1.2 or above?",
            matched_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
        ),
        error_message=None,
        extensions={},
    )

    assert response.original_question == "Do you support TLS 1.2 or above?"
    assert response.generated_answer.startswith("Yes.")
    assert response.domain_tag == "security"
    assert response.confidence_level == "high"
    assert response.historical_alignment_indicator is True
    assert response.reference is not None
    assert response.reference.source_doc == "historical_repository_qa.csv"


def test_tender_response_summary_contains_required_batch_fields() -> None:
    summary = TenderResponseSummary(
        total_questions_processed=12,
        flagged_high_risk_or_inconsistent_responses=2,
        overall_completion_status="completed_with_flags",
        completed_questions=11,
        failed_questions=1,
    )

    assert summary.total_questions_processed == 12
    assert summary.flagged_high_risk_or_inconsistent_responses == 2
    assert summary.overall_completion_status == "completed_with_flags"


def test_workflow_response_supports_stable_and_extensible_json_contract() -> None:
    response = TenderResponseWorkflowResponse(
        request_id="req-123",
        session_id="session-123",
        source_file_name="tender_questions.csv",
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
                    alignment_record_id="qa_123",
                    alignment_score=0.92,
                ),
                reference=QuestionReference(
                    alignment_record_id="qa_123",
                    alignment_score=0.92,
                    source_doc="historical_repository_qa.csv",
                    matched_question="Do you support TLS 1.2 or above?",
                    matched_answer="Yes.",
                ),
                error_message=None,
                extensions={"future_field": "supported"},
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

    assert response.total_questions_processed == 1
    assert response.questions[0].extensions == {"future_field": "supported"}
    assert response.questions[0].reference is not None
    assert response.questions[0].reference.matched_answer == "Yes."
    assert response.summary.overall_completion_status == "completed"
