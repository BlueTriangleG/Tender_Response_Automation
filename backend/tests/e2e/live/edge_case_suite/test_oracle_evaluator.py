from tests.e2e.live.edge_case_suite.oracle_evaluator import evaluate_oracle


def test_evaluate_oracle_allows_negated_forbidden_phrase() -> None:
    result = evaluate_oracle(
        "case-1",
        {
            "expected_summary": {},
            "questions": [
                {
                    "question_id": "q-1",
                    "must_not_include": ["FedRAMP High authorized"],
                }
            ],
        },
        {
            "total_questions_processed": 1,
            "summary": {
                "total_questions_processed": 1,
                "overall_completion_status": "completed",
                "completed_questions": 1,
                "unanswered_questions": 0,
                "failed_questions": 0,
            },
            "questions": [
                {
                    "question_id": "q-1",
                    "status": "completed",
                    "grounding_status": "grounded",
                    "historical_alignment_indicator": True,
                    "generated_answer": (
                        "I cannot confirm the platform is FedRAMP High authorized "
                        "for this environment."
                    ),
                    "domain_tag": "compliance",
                    "references": [],
                }
            ],
        },
    )

    assert result.passed is True


def test_evaluate_oracle_rejects_positive_forbidden_phrase() -> None:
    result = evaluate_oracle(
        "case-2",
        {
            "expected_summary": {},
            "questions": [
                {
                    "question_id": "q-1",
                    "must_not_include": ["FedRAMP High authorized"],
                }
            ],
        },
        {
            "total_questions_processed": 1,
            "summary": {
                "total_questions_processed": 1,
                "overall_completion_status": "completed",
                "completed_questions": 1,
                "unanswered_questions": 0,
                "failed_questions": 0,
            },
            "questions": [
                {
                    "question_id": "q-1",
                    "status": "completed",
                    "grounding_status": "grounded",
                    "historical_alignment_indicator": True,
                    "generated_answer": "The platform is FedRAMP High authorized.",
                    "domain_tag": "compliance",
                    "references": [],
                }
            ],
        },
    )

    assert result.passed is False
    assert result.errors == [
        "q-1: generated answer included forbidden phrase 'FedRAMP High authorized'"
    ]


def test_evaluate_oracle_allows_unicode_apostrophe_negated_forbidden_phrase() -> None:
    result = evaluate_oracle(
        "case-3",
        {
            "expected_summary": {},
            "questions": [
                {
                    "question_id": "q-1",
                    "must_not_include": ["FedRAMP High authorized"],
                }
            ],
        },
        {
            "total_questions_processed": 1,
            "summary": {
                "total_questions_processed": 1,
                "overall_completion_status": "completed",
                "completed_questions": 1,
                "unanswered_questions": 0,
                "failed_questions": 0,
            },
            "questions": [
                {
                    "question_id": "q-1",
                    "status": "completed",
                    "grounding_status": "partial_reference",
                    "historical_alignment_indicator": True,
                    "generated_answer": (
                        "I can’t confirm that the platform is FedRAMP High authorized "
                        "for the proposed environment."
                    ),
                    "domain_tag": "compliance",
                    "references": [],
                }
            ],
        },
    )

    assert result.passed is True
