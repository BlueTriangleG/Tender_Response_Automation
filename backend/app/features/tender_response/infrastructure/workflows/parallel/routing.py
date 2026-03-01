"""Routing helpers for the parallel tender-response workflow."""

from langgraph.types import Send

from app.features.tender_response.infrastructure.workflows.common.state import (
    BatchTenderResponseState,
    QuestionProcessingState,
)


def route_after_assessment(state: QuestionProcessingState) -> str:
    """Branch to grounded generation only when references are sufficient."""

    assessment = state["current_assessment"]
    if assessment.can_answer and assessment.usable_reference_ids:
        return "generate_answer"
    return "finalize_unanswered"


def dispatch_questions(state: BatchTenderResponseState) -> list[Send]:
    """Fan out one processing task per question for parallel execution."""

    return [
        Send(
            "process_question",
            {
                "current_question": question,
                "alignment_threshold": state["alignment_threshold"],
            },
        )
        for question in state["questions"]
    ]
