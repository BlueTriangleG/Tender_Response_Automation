"""Regression tests for workflow state reducers."""

from app.features.tender_response.infrastructure.workflows.common.state import (
    _extend_conflict_findings,
    _extend_errors,
    _extend_question_results,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionRisk,
    TenderQuestionResponse,
)


def _make_question_result(question_id: str) -> TenderQuestionResponse:
    """Build a minimal completed response row for reducer tests."""

    return TenderQuestionResponse(
        question_id=question_id,
        original_question=f"Question {question_id}",
        generated_answer=f"Answer {question_id}",
        domain_tag="security",
        confidence_level="high",
        confidence_reason="Direct support.",
        historical_alignment_indicator=True,
        status="completed",
        grounding_status="grounded",
        flags=QuestionFlags(),
        risk=QuestionRisk(level="low", reason="Low risk."),
        metadata=QuestionMetadata(source_row_index=0, alignment_record_id=f"qa-{question_id}"),
        references=[],
        error_message=None,
        extensions={},
    )


def test_extend_question_results_keeps_existing_items_when_right_is_empty() -> None:
    """Reducer should preserve accumulated results on empty writes."""

    left = [_make_question_result("q-1")]

    merged = _extend_question_results(left, [])

    assert merged == left


def test_extend_errors_keeps_existing_items_when_right_is_empty() -> None:
    """Reducer should preserve accumulated run errors on empty writes."""

    left = ["q-1: generation failed"]

    merged = _extend_errors(left, [])

    assert merged == left


def test_extend_conflict_findings_keeps_existing_items_when_right_is_empty() -> None:
    """Reducer should preserve accumulated conflict findings on empty writes."""

    left = [
        {
            "target_question_id": "q-1",
            "conflicting_question_id": "q-2",
            "reason": "Conflicting commitments.",
            "severity": "high",
        }
    ]

    merged = _extend_conflict_findings(left, [])

    assert merged == left
