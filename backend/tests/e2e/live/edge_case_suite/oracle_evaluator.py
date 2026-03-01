"""Behavioral oracle evaluation for live tender-response results."""

from __future__ import annotations

from typing import Any

from tests.e2e.live.edge_case_suite.models import EvaluationResult

_NEGATION_OR_REFUSAL_MARKERS = (
    "not ",
    "cannot",
    "can't",
    "cannot confirm",
    "can't confirm",
    "do not",
    "does not",
    "no evidence",
    "unsupported",
    "not approved",
    "must not",
)


def _normalize_text(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _window_around_phrase(text: str, phrase: str, *, padding: int = 64) -> str:
    index = text.find(phrase)
    if index == -1:
        return ""
    start = max(index - padding, 0)
    end = min(index + len(phrase) + padding, len(text))
    return text[start:end]


def _is_negated_or_refused_phrase(answer_text: str, phrase: str) -> bool:
    window = _window_around_phrase(
        _normalize_text(answer_text).lower(),
        _normalize_text(phrase).lower(),
    )
    return any(marker in window for marker in _NEGATION_OR_REFUSAL_MARKERS)


def _assert_summary(
    errors: list[str],
    oracle_summary: dict[str, Any],
    actual_payload: dict[str, Any],
) -> None:
    actual_summary = actual_payload["summary"]

    expected_total = oracle_summary.get("total_questions_processed")
    if expected_total is not None and actual_payload["total_questions_processed"] != expected_total:
        errors.append(
            "total_questions_processed mismatch: "
            f"expected {expected_total}, got {actual_payload['total_questions_processed']}"
        )

    allowed_statuses = oracle_summary.get("allowed_overall_completion_statuses", [])
    if allowed_statuses and actual_summary["overall_completion_status"] not in allowed_statuses:
        errors.append(
            "overall_completion_status mismatch: "
            f"expected one of {allowed_statuses}, got "
            f"{actual_summary['overall_completion_status']}"
        )

    for key in ("completed", "unanswered", "failed"):
        min_value = oracle_summary.get(f"{key}_min")
        max_value = oracle_summary.get(f"{key}_max")
        actual_value = actual_summary[f"{key}_questions"]

        if min_value is not None and actual_value < min_value:
            errors.append(
                f"{key}_questions below minimum: expected >= {min_value}, got {actual_value}"
            )
        if max_value is not None and actual_value > max_value:
            errors.append(
                f"{key}_questions above maximum: expected <= {max_value}, got {actual_value}"
            )


def _assert_question(
    errors: list[str],
    question_oracle: dict[str, Any],
    actual_question: dict[str, Any],
) -> None:
    question_id = question_oracle["question_id"]

    expected_status = question_oracle.get("expected_status")
    if expected_status and actual_question["status"] != expected_status:
        errors.append(
            f"{question_id}: expected status {expected_status}, got {actual_question['status']}"
        )

    allowed_statuses = question_oracle.get("allowed_statuses")
    if allowed_statuses and actual_question["status"] not in allowed_statuses:
        errors.append(
            f"{question_id}: expected status in {allowed_statuses}, got {actual_question['status']}"
        )

    expected_grounding_status = question_oracle.get("expected_grounding_status")
    if (
        expected_grounding_status
        and actual_question["grounding_status"] != expected_grounding_status
    ):
        errors.append(
            f"{question_id}: expected grounding_status {expected_grounding_status}, "
            f"got {actual_question['grounding_status']}"
        )

    allowed_grounding_statuses = question_oracle.get("allowed_grounding_statuses")
    if (
        allowed_grounding_statuses
        and actual_question["grounding_status"] not in allowed_grounding_statuses
    ):
        errors.append(
            f"{question_id}: expected grounding_status in {allowed_grounding_statuses}, "
            f"got {actual_question['grounding_status']}"
        )

    expected_alignment = question_oracle.get("expected_historical_alignment_indicator")
    if (
        expected_alignment is not None
        and actual_question["historical_alignment_indicator"] != expected_alignment
    ):
        errors.append(
            f"{question_id}: expected historical_alignment_indicator={expected_alignment}, "
            f"got {actual_question['historical_alignment_indicator']}"
        )

    expected_null_answer = question_oracle.get("generated_answer_should_be_null")
    if expected_null_answer is True and actual_question["generated_answer"] is not None:
        errors.append(f"{question_id}: expected generated_answer to be null")
    if expected_null_answer is False and actual_question["generated_answer"] is None:
        errors.append(f"{question_id}: expected generated_answer to be non-null")

    allowed_domain_tags = question_oracle.get("allowed_domain_tags")
    if allowed_domain_tags and actual_question["domain_tag"] not in allowed_domain_tags:
        errors.append(
            f"{question_id}: expected domain_tag in {allowed_domain_tags}, "
            f"got {actual_question['domain_tag']}"
        )

    references = actual_question.get("references", [])
    reference_count_min = question_oracle.get("reference_count_min")
    reference_count_max = question_oracle.get("reference_count_max")
    if reference_count_min is not None and len(references) < reference_count_min:
        errors.append(
            f"{question_id}: expected at least {reference_count_min} references, "
            f"got {len(references)}"
        )
    if reference_count_max is not None and len(references) > reference_count_max:
        errors.append(
            f"{question_id}: expected at most {reference_count_max} references, "
            f"got {len(references)}"
        )

    answer_text = actual_question.get("generated_answer") or ""
    must_include_any = question_oracle.get("must_include_any", [])
    if must_include_any and not any(needle in answer_text for needle in must_include_any):
        errors.append(f"{question_id}: generated answer did not include any of {must_include_any}")

    must_not_include = question_oracle.get("must_not_include", [])
    normalized_answer_text = _normalize_text(answer_text)
    violating_phrase = next(
        (
            needle
            for needle in must_not_include
            if _normalize_text(needle) in normalized_answer_text
            and not _is_negated_or_refused_phrase(answer_text, needle)
        ),
        None,
    )
    if violating_phrase:
        errors.append(
            f"{question_id}: generated answer included forbidden phrase {violating_phrase!r}"
        )


def evaluate_oracle(
    case_id: str,
    oracle: dict[str, Any],
    actual_payload: dict[str, Any],
) -> EvaluationResult:
    """Compare one actual tender-response payload against one oracle."""

    errors: list[str] = []

    _assert_summary(errors, oracle.get("expected_summary", {}), actual_payload)

    actual_questions = {
        question["question_id"]: question for question in actual_payload.get("questions", [])
    }
    for question_oracle in oracle.get("questions", []):
        question_id = question_oracle["question_id"]
        actual_question = actual_questions.get(question_id)
        if actual_question is None:
            errors.append(f"{question_id}: missing from actual response")
            continue
        _assert_question(errors, question_oracle, actual_question)

    return EvaluationResult(case_id=case_id, passed=not errors, errors=errors)
