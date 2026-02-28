from app.schemas.history_ingest import (
    HistoryIngestResponse,
    HistoryIngestRequestOptions,
    ParsedFilePayload,
    ProcessedHistoryFileResult,
)


def test_parsed_file_payload_supports_common_fields() -> None:
    payload = ParsedFilePayload(
        file_name="history.json",
        extension=".json",
        content_type="application/json",
        size_bytes=42,
        parsed_kind="json",
        raw_text='{"hello": "world"}',
        structured_data={"hello": "world"},
        row_count=1,
        warnings=[],
    )

    assert payload.file_name == "history.json"
    assert payload.extension == ".json"
    assert payload.parsed_kind == "json"
    assert payload.structured_data == {"hello": "world"}
    assert payload.row_count == 1


def test_processed_history_file_result_supports_success_and_failure() -> None:
    success = ProcessedHistoryFileResult(
        status="processed",
        payload=ParsedFilePayload(
            file_name="policy.md",
            extension=".md",
            content_type="text/markdown",
            size_bytes=10,
            parsed_kind="markdown",
            raw_text="# Title",
            structured_data=None,
            row_count=None,
            warnings=[],
        ),
        error_code=None,
        error_message=None,
    )
    failure = ProcessedHistoryFileResult(
        status="failed",
        payload=None,
        error_code="unsupported_extension",
        error_message="Unsupported file type: .pdf",
    )

    assert success.status == "processed"
    assert success.payload is not None
    assert failure.status == "failed"
    assert failure.payload is None
    assert failure.error_code == "unsupported_extension"


def test_history_ingest_response_supports_batch_summary_counters() -> None:
    response = HistoryIngestResponse(
        request_id="req-123",
        total_file_count=3,
        processed_file_count=2,
        failed_file_count=1,
        request_options=HistoryIngestRequestOptions(
            output_format="excel",
            similarity_threshold=0.81,
        ),
        files=[
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="history.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=25,
                    parsed_kind="csv",
                    raw_text="name\nalice",
                    structured_data=[{"name": "alice"}],
                    row_count=1,
                    warnings=[],
                ),
                error_code=None,
                error_message=None,
            )
        ],
    )

    assert response.request_id == "req-123"
    assert response.total_file_count == 3
    assert response.processed_file_count == 2
    assert response.failed_file_count == 1
    assert response.request_options.output_format == "excel"
    assert response.request_options.similarity_threshold == 0.81
    assert len(response.files) == 1


def test_history_ingest_request_options_defaults_match_frontend_upload_flow() -> None:
    options = HistoryIngestRequestOptions()

    assert options.output_format == "json"
    assert options.similarity_threshold == 0.72
