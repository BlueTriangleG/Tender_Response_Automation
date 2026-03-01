import pytest

from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
    TenderResponseWorkflowResponse,
)
from pydantic import ValidationError


def test_tender_question_response_contains_required_business_fields() -> None:
    response = TenderQuestionResponse(
        question_id="q-001",
        original_question="Do you support TLS 1.2 or above?",
        generated_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
        domain_tag="security",
        confidence_level="high",
        confidence_reason="Historical references directly support the response.",
        historical_alignment_indicator=True,
        status="completed",
        grounding_status="grounded",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(level="medium", reason="Security assurance statements require review."),
        metadata=QuestionMetadata(
            source_row_index=0,
            alignment_record_id="qa_123",
            alignment_score=0.92,
        ),
        references=[
            QuestionReference(
                alignment_record_id="qa_123",
                alignment_score=0.92,
                source_doc="historical_repository_qa.csv",
                matched_question="Do you support TLS 1.2 or above?",
                matched_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                used_for_answer=True,
            )
        ],
        error_message=None,
        extensions={},
    )

    assert response.original_question == "Do you support TLS 1.2 or above?"
    assert response.generated_answer.startswith("Yes.")
    assert response.domain_tag == "security"
    assert response.confidence_level == "high"
    assert response.confidence_reason is not None
    assert response.historical_alignment_indicator is True
    assert response.grounding_status == "grounded"
    assert response.risk.level == "medium"
    assert response.references[0].source_doc == "historical_repository_qa.csv"


def test_tender_response_summary_contains_required_batch_fields() -> None:
    summary = TenderResponseSummary(
        total_questions_processed=12,
        flagged_high_risk_or_inconsistent_responses=2,
        overall_completion_status="completed_with_flags",
        completed_questions=11,
        unanswered_questions=0,
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
                confidence_reason="Historical references directly support the response.",
                historical_alignment_indicator=True,
                status="completed",
                grounding_status="grounded",
                flags=QuestionFlags(high_risk=False, inconsistent_response=False),
                risk=QuestionRisk(
                    level="medium",
                    reason="Security assurance statements require review.",
                ),
                metadata=QuestionMetadata(
                    source_row_index=0,
                    alignment_record_id="qa_123",
                    alignment_score=0.92,
                ),
                references=[
                    QuestionReference(
                        alignment_record_id="qa_123",
                        alignment_score=0.92,
                        source_doc="historical_repository_qa.csv",
                        matched_question="Do you support TLS 1.2 or above?",
                        matched_answer="Yes.",
                        used_for_answer=True,
                    )
                ],
                error_message=None,
                extensions={"future_field": "supported"},
            )
        ],
        summary=TenderResponseSummary(
            total_questions_processed=1,
            flagged_high_risk_or_inconsistent_responses=0,
            overall_completion_status="completed",
            completed_questions=1,
            unanswered_questions=0,
            failed_questions=0,
        ),
    )

    assert response.total_questions_processed == 1
    assert response.questions[0].extensions == {"future_field": "supported"}
    assert response.questions[0].references[0].matched_answer == "Yes."
    assert response.summary.overall_completion_status == "completed"


def test_unanswered_response_accepts_null_confidence_fields() -> None:
    response = TenderQuestionResponse(
        question_id="q-002",
        original_question="Are you FedRAMP authorised?",
        generated_answer=None,
        domain_tag="compliance",
        confidence_level=None,
        confidence_reason=None,
        historical_alignment_indicator=False,
        status="unanswered",
        grounding_status="no_reference",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(level="low", reason="No grounded answer was produced."),
        metadata=QuestionMetadata(
            source_row_index=1,
            alignment_record_id=None,
            alignment_score=None,
        ),
        references=[],
        error_message=None,
        extensions={},
    )

    assert response.status == "unanswered"
    assert response.confidence_level is None
    assert response.confidence_reason is None


def test_unanswered_response_rejects_empty_confidence_reason() -> None:
    with pytest.raises(ValidationError):
        TenderQuestionResponse(
            question_id="q-003",
            original_question="Do you hold an active IRAP assessment?",
            generated_answer=None,
            domain_tag="compliance",
            confidence_level=None,
            confidence_reason="",
            historical_alignment_indicator=False,
            status="unanswered",
            grounding_status="no_reference",
            flags=QuestionFlags(high_risk=False, inconsistent_response=False),
            risk=QuestionRisk(level="low", reason="No grounded answer was produced."),
            metadata=QuestionMetadata(
                source_row_index=2,
                alignment_record_id=None,
                alignment_score=None,
            ),
            references=[],
            error_message=None,
            extensions={},
        )


def test_completed_partial_reference_response_supports_partial_answer_contract() -> None:
    response = TenderQuestionResponse(
        question_id="q-004",
        original_question="Describe your sovereign hosting guarantees.",
        generated_answer=(
            "We can support regional hosting controls (jurisdiction-specific sovereign "
            "hosting guarantees are not evidenced in the retrieved references)."
        ),
        domain_tag="compliance",
        confidence_level="medium",
        confidence_reason=(
            "Confidence is reduced because the retrieved references support regional "
            "hosting controls but do not evidence jurisdiction-specific sovereign "
            "hosting guarantees or contractual commitments."
        ),
        historical_alignment_indicator=True,
        status="completed",
        grounding_status="partial_reference",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(
            level="medium",
            reason="Review is required before making sovereign hosting commitments.",
        ),
        metadata=QuestionMetadata(
            source_row_index=3,
            alignment_record_id="qa_456",
            alignment_score=0.68,
        ),
        references=[
            QuestionReference(
                alignment_record_id="qa_456",
                alignment_score=0.68,
                source_doc="compliance-history.csv",
                matched_question="Describe your hosting controls.",
                matched_answer="Regional hosting controls are available by deployment.",
                used_for_answer=True,
            )
        ],
        error_message=None,
        extensions={},
    )

    assert response.status == "completed"
    assert response.grounding_status == "partial_reference"
    assert response.generated_answer is not None
    assert "(" in response.generated_answer and ")" in response.generated_answer
    assert response.confidence_level == "medium"
    assert "Confidence is reduced because" in response.confidence_reason
    assert "do not evidence jurisdiction-specific sovereign hosting guarantees" in (
        response.confidence_reason or ""
    )
