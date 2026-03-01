"""Routing helpers for the parallel tender-response workflow."""

from langgraph.types import Send

from app.features.tender_response.infrastructure.workflows.common.state import (
    BatchTenderResponseState,
    QuestionProcessingState,
)


def route_after_assessment(state: QuestionProcessingState) -> str:
    """Branch to grounded generation only when references are sufficient."""

    assessment = state["current_assessment"]
    if (
        assessment.can_answer
        and assessment.usable_reference_ids
        and assessment.grounding_status in {"grounded", "partial_reference"}
    ):
        return "generate_answer"
    return "finalize_unanswered"


def route_after_output_validation(state: QuestionProcessingState) -> str:
    """Route completed outputs, recoverable retries, or exhausted failures."""

    if state.get("current_result") is not None:
        return "__end__"
    if state.get("generation_validation_error") and state.get("generation_attempt_count", 0) < 3:
        return "generate_answer"
    return "fail_generation"


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


def dispatch_conflict_review_jobs(state: BatchTenderResponseState) -> list[Send] | str:
    """Fan out session conflict review across groups of up to ten target questions."""

    current_completed_ids = [
        result.question_id
        for result in state["question_results"]
        if result.status == "completed" and (result.generated_answer or "").strip()
    ]
    if not current_completed_ids:
        return "apply_conflicts"

    reference_ids = {
        result.question_id
        for result in [*state.get("session_completed_results", []), *state["question_results"]]
        if result.status == "completed" and (result.generated_answer or "").strip()
    }
    if len(reference_ids) < 2:
        return "apply_conflicts"

    return [
        Send(
            "review_conflict_group",
            {
                "question_results": state["question_results"],
                "session_completed_results": state.get("session_completed_results", []),
                "current_conflict_job": {
                    "target_question_ids": current_completed_ids[index : index + 10]
                },
            },
        )
        for index in range(0, len(current_completed_ids), 10)
    ]
