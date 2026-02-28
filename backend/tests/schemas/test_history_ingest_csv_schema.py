from app.features.history_ingest.schemas.responses import (
    DetectedCsvColumns,
    HistoryIngestResponse,
    ParsedFilePayload,
    ProcessedHistoryFileResult,
)


def test_detected_csv_columns_supports_required_targets() -> None:
    columns = DetectedCsvColumns(
        question_col="question_text",
        answer_col="approved_answer",
        domain_col="domain",
    )

    assert columns.question_col == "question_text"
    assert columns.answer_col == "approved_answer"
    assert columns.domain_col == "domain"


def test_processed_history_file_result_supports_csv_ingest_metadata() -> None:
    result = ProcessedHistoryFileResult(
        status="processed",
        payload=ParsedFilePayload(
            file_name="history.csv",
            extension=".csv",
            content_type="text/csv",
            size_bytes=128,
            parsed_kind="csv",
            raw_text="question,answer,domain\nQ,A,Security",
            structured_data=[{"question": "Q", "answer": "A", "domain": "Security"}],
            row_count=1,
            warnings=[],
        ),
        error_code=None,
        error_message=None,
        detected_columns=DetectedCsvColumns(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
        ),
        ingested_row_count=1,
        failed_row_count=0,
        storage_target="qa_records",
    )

    assert result.detected_columns is not None
    assert result.detected_columns.question_col == "question"
    assert result.ingested_row_count == 1
    assert result.failed_row_count == 0
    assert result.storage_target == "qa_records"


def test_history_ingest_response_keeps_batch_results_with_extended_file_metadata() -> None:
    response = HistoryIngestResponse(
        total_file_count=2,
        processed_file_count=1,
        failed_file_count=1,
        files=[
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="good.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=32,
                    parsed_kind="csv",
                    raw_text="question,answer,domain",
                    structured_data=[],
                    row_count=0,
                    warnings=[],
                ),
                error_code=None,
                error_message=None,
                detected_columns=DetectedCsvColumns(
                    question_col="question",
                    answer_col="answer",
                    domain_col="domain",
                ),
                ingested_row_count=0,
                failed_row_count=0,
                storage_target="qa_records",
            ),
            ProcessedHistoryFileResult(
                status="failed",
                payload=None,
                error_code="column_mapping_failed",
                error_message="Could not determine CSV columns.",
                detected_columns=None,
                ingested_row_count=0,
                failed_row_count=1,
                storage_target=None,
            ),
        ],
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 1
    assert response.failed_file_count == 1
    assert response.files[0].storage_target == "qa_records"
    assert response.files[1].error_code == "column_mapping_failed"
