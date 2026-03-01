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


def dispatch_questions(state: BatchTenderResponseState) -> list[Send] | str:
    """Fan out one processing task per question for parallel execution.

    Returns a direct route to 'summarize_batch' when the question list is
    empty so that the summary node always runs and ``result['summary']``
    is never ``None`` after ``ainvoke`` returns.
    """

    if not state["questions"]:
        return "summarize_batch"

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
