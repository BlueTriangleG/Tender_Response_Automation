from app.schemas.history_ingest import DetectedCsvColumns
from app.services.csv_qa_normalization_service import CsvQaNormalizationService


def test_normalize_rows_maps_csv_rows_into_qa_records() -> None:
    service = CsvQaNormalizationService()

    result = service.normalize_rows(
        file_name="history.csv",
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        rows=[
            {"question": "What is TLS?", "answer": "TLS 1.2+", "domain": "Security"},
        ],
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.question == "What is TLS?"
    assert record.answer == "TLS 1.2+"
    assert record.domain == "Security"
    assert record.source_doc == "history.csv"
    assert record.client is None
    assert record.tags == []
    assert record.risk_topics == []


def test_normalize_rows_builds_deterministic_text() -> None:
    service = CsvQaNormalizationService()

    result = service.normalize_rows(
        file_name="history.csv",
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        rows=[
            {"question": "Q", "answer": "A", "domain": "Security"},
        ],
    )

    assert result.records[0].text == "Question: Q\nAnswer: A\nDomain: Security"


def test_normalize_rows_generates_stable_ids_for_file_and_row_index() -> None:
    service = CsvQaNormalizationService()

    result_one = service.normalize_rows(
        file_name="history.csv",
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        rows=[{"question": "Q", "answer": "A", "domain": "Security"}],
    )
    result_two = service.normalize_rows(
        file_name="history.csv",
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        rows=[{"question": "Q", "answer": "A", "domain": "Security"}],
    )

    assert result_one.records[0].id == result_two.records[0].id


def test_normalize_rows_rejects_rows_with_blank_required_fields() -> None:
    service = CsvQaNormalizationService()

    result = service.normalize_rows(
        file_name="history.csv",
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        rows=[
            {"question": "Q", "answer": "", "domain": "Security"},
            {"question": "Q2", "answer": "A2", "domain": "AI"},
        ],
    )

    assert len(result.records) == 1
    assert result.failed_row_count == 1
    assert result.records[0].question == "Q2"
