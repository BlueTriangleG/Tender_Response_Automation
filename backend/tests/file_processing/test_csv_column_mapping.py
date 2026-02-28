from app.features.history_ingest.domain.csv_column_mapping import (
    CsvColumnMappingResult,
    infer_csv_columns_from_headers,
)


def test_infer_csv_columns_matches_exact_synonyms() -> None:
    result = infer_csv_columns_from_headers(["question", "approved_answer", "domain"])

    assert result == CsvColumnMappingResult(
        question_col="question",
        answer_col="approved_answer",
        domain_col="domain",
        unresolved_targets=[],
        ambiguous_targets=[],
    )


def test_infer_csv_columns_normalizes_headers_case_insensitively() -> None:
    result = infer_csv_columns_from_headers(
        ["Question Text", "Suggested_Answer", "Practice Area"]
    )

    assert result.question_col == "Question Text"
    assert result.answer_col == "Suggested_Answer"
    assert result.domain_col == "Practice Area"
    assert result.unresolved_targets == []
    assert result.ambiguous_targets == []


def test_infer_csv_columns_flags_ambiguous_targets_instead_of_guessing() -> None:
    result = infer_csv_columns_from_headers(
        ["question", "customer_question", "answer", "domain"]
    )

    assert result.question_col is None
    assert result.answer_col == "answer"
    assert result.domain_col == "domain"
    assert result.ambiguous_targets == ["question"]


def test_infer_csv_columns_flags_missing_required_targets() -> None:
    result = infer_csv_columns_from_headers(["answer", "topic"])

    assert result.question_col is None
    assert result.answer_col == "answer"
    assert result.domain_col is None
    assert result.unresolved_targets == ["question", "domain"]
