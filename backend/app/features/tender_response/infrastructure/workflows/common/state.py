"""Shared state types and reducers for tender-response workflows."""

from typing import Annotated, TypedDict

from app.features.tender_response.domain.models import (
    GroundedAnswerResult,
    HistoricalAlignmentResult,
    ReferenceAssessmentResult,
    TenderQuestion,
)
from app.features.tender_response.schemas.responses import (
    TenderQuestionResponse,
    TenderResponseSummary,
)


def _extend_question_results(
    left: list[TenderQuestionResponse],
    right: list[TenderQuestionResponse],
) -> list[TenderQuestionResponse]:
    return left + right


def _extend_errors(left: list[str], right: list[str]) -> list[str]:
    return left + right


class ReviewPayload(TypedDict):
    """Typed intermediate state written by generate_answer, read by assess_output."""

    confidence_level: str
    confidence_reason: str
    risk_level: str
    risk_reason: str
    inconsistent_response: bool


class BatchTenderResponseState(TypedDict):
    """State for the outer batch workflow.

    Only fields that are read or written at the batch level belong here.
    Per-question intermediate fields (alignment, assessment, review, …) live
    exclusively in QuestionProcessingState so this schema stays uncluttered.
    """

    request_id: str
    session_id: str | None
    source_file_name: str
    alignment_threshold: float
    questions: list[TenderQuestion]
    question_results: Annotated[list[TenderQuestionResponse], _extend_question_results]
    run_errors: Annotated[list[str], _extend_errors]
    summary: TenderResponseSummary | None
    # Populated per-Send by dispatch_questions; read by process_question.
    current_question: TenderQuestion | None


class QuestionProcessingState(TypedDict):
    """State for one isolated tender question inside the parallel workflow."""

    current_question: TenderQuestion
    alignment_threshold: float
    current_alignment: HistoricalAlignmentResult | None
    current_assessment: ReferenceAssessmentResult | None
    current_review: ReviewPayload | None
    current_grounded_result: GroundedAnswerResult | None
    current_answer: str | None
    generation_attempt_count: int
    generation_validation_error: str | None
    generation_retry_history: list[str]
    last_invalid_answer: str | None
    last_invalid_confidence_level: str | None
    last_invalid_confidence_reason: str | None
    current_result: TenderQuestionResponse | None
