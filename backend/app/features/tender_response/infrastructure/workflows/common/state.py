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
    if not right:
        return []

    merged_by_id: dict[str, TenderQuestionResponse] = {}
    order: list[str] = []
    for item in [*left, *right]:
        if item.question_id not in merged_by_id:
            order.append(item.question_id)
        merged_by_id[item.question_id] = item
    return [merged_by_id[question_id] for question_id in order]


def _extend_errors(left: list[str], right: list[str]) -> list[str]:
    if not right:
        return []
    return left + right


def _extend_conflict_findings(left: list[dict], right: list[dict]) -> list[dict]:
    if not right:
        return []
    return left + right


class ReviewPayload(TypedDict):
    """Typed intermediate state written by generate_answer, read by assess_output."""

    confidence_level: str
    confidence_reason: str
    risk_level: str
    risk_reason: str
    inconsistent_response: bool


class ConflictReviewJob(TypedDict):
    """One parallel conflict-review assignment over up to ten target questions."""

    target_question_ids: list[str]


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
    session_completed_results: list[TenderQuestionResponse]
    conflict_findings: Annotated[list[dict], _extend_conflict_findings]
    conflict_review_errors: Annotated[list[str], _extend_errors]
    run_errors: Annotated[list[str], _extend_errors]
    summary: TenderResponseSummary | None
    # Populated per-Send by dispatch_questions; read by process_question.
    current_question: TenderQuestion | None
    current_conflict_job: ConflictReviewJob | None


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
