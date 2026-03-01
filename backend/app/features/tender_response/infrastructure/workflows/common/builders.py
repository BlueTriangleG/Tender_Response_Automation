"""Shared result builders for tender-response workflows."""

from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    HistoricalReference,
    ReferenceAssessmentResult,
    TenderQuestion,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
)


def build_reference_payload(
    references: list[HistoricalReference],
    *,
    used_reference_ids: set[str] | None = None,
) -> list[QuestionReference]:
    """Convert alignment references into the public API response shape."""

    used_ids = used_reference_ids or set()
    return [
        QuestionReference(
            alignment_record_id=reference.record_id,
            reference_type=reference.reference_type,
            alignment_score=reference.alignment_score,
            source_doc=reference.source_doc,
            matched_question=reference.question,
            matched_answer=reference.answer,
            excerpt=reference.excerpt,
            chunk_index=reference.chunk_index,
            used_for_answer=reference.record_id in used_ids,
        )
        for reference in references
    ]


def primary_domain_tag(
    *,
    question: TenderQuestion,
    alignment: HistoricalAlignmentResult,
    domain_tagging_service: DomainTaggingService,
) -> str:
    """Resolve the domain tag for results that do not keep a generated answer."""

    return domain_tagging_service.tag(
        question=question,
        generated_answer="",
        alignment=alignment,
    )


def unanswered_confidence_reason(
    *,
    assessment: ReferenceAssessmentResult,
    alignment: HistoricalAlignmentResult,
) -> str:
    """Choose the confidence explanation for unanswered questions."""

    if assessment.grounding_status == "no_reference" or not alignment.references:
        return "Insufficient supporting evidence to answer safely."
    return assessment.reason


def failed_question_result(question: TenderQuestion, error_message: str) -> TenderQuestionResponse:
    """Materialize a failed question result without crashing the batch."""

    return TenderQuestionResponse(
        question_id=question.question_id,
        original_question=question.original_question,
        generated_answer=None,
        domain_tag=question.declared_domain or "unknown",
        confidence_level="low",
        confidence_reason="The question failed before a grounded answer could be produced.",
        historical_alignment_indicator=False,
        status="failed",
        grounding_status="failed",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(level="low", reason="No answer was generated."),
        metadata=QuestionMetadata(
            source_row_index=question.source_row_index,
            alignment_record_id=None,
            alignment_score=None,
        ),
        references=[],
        error_message=error_message,
        extensions={},
    )
