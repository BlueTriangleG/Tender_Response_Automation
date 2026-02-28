from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.features.history_ingest.api.dependencies import get_history_ingest_use_case
from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions
from app.features.history_ingest.schemas.responses import (
    DetectedCsvColumns,
    HistoryIngestResponse,
    ParsedFilePayload,
    ProcessedHistoryFileResult,
)
from app.main import app


def test_history_ingest_route_accepts_single_upload_tender_file() -> None:
    client = TestClient(app)
    mock_use_case = MagicMock()

    mocked_response = HistoryIngestResponse(
        total_file_count=1,
        processed_file_count=1,
        failed_file_count=0,
        request_options=HistoryIngestRequestOptions(
            output_format="excel",
            similarity_threshold=0.81,
        ),
        files=[
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="tender.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=64,
                    parsed_kind="csv",
                    raw_text="question,answer,domain\nQ,A,Security\n",
                    structured_data=[{"question": "Q", "answer": "A", "domain": "Security"}],
                    row_count=1,
                    warnings=[],
                ),
                detected_columns=DetectedCsvColumns(
                    question_col="question",
                    answer_col="answer",
                    domain_col="domain",
                ),
                ingested_row_count=1,
                failed_row_count=0,
                storage_target="qa_records",
            )
        ],
    )

    mock_use_case.process_files = AsyncMock(return_value=mocked_response)
    app.dependency_overrides[get_history_ingest_use_case] = lambda: mock_use_case
    try:
        response = client.post(
            "/api/ingest/history",
            files={
                "file": (
                    "tender.csv",
                    b"question,answer,domain\nQ,A,Security\n",
                    "text/csv",
                )
            },
            data={
                "outputFormat": "excel",
                "similarityThreshold": "0.81",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_file_count"] == 1
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 0
    assert payload["request_options"] == {
        "output_format": "excel",
        "similarity_threshold": 0.81,
    }
    assert payload["files"][0]["payload"]["file_name"] == "tender.csv"
    assert payload["files"][0]["detected_columns"] == {
        "question_col": "question",
        "answer_col": "answer",
        "domain_col": "domain",
    }
    assert payload["files"][0]["ingested_row_count"] == 1
    assert payload["files"][0]["storage_target"] == "qa_records"


def test_history_ingest_route_accepts_batch_files_under_files_field() -> None:
    client = TestClient(app)
    mock_use_case = MagicMock()

    mocked_response = HistoryIngestResponse(
        total_file_count=2,
        processed_file_count=1,
        failed_file_count=1,
        files=[
            ProcessedHistoryFileResult(
                status="processed",
                payload=ParsedFilePayload(
                    file_name="history.csv",
                    extension=".csv",
                    content_type="text/csv",
                    size_bytes=64,
                    parsed_kind="csv",
                    raw_text="question,answer,domain\nQ,A,Security\n",
                    structured_data=[{"question": "Q", "answer": "A", "domain": "Security"}],
                    row_count=1,
                    warnings=[],
                ),
                detected_columns=DetectedCsvColumns(
                    question_col="question",
                    answer_col="answer",
                    domain_col="domain",
                ),
                ingested_row_count=1,
                failed_row_count=0,
                storage_target="qa_records",
            ),
            ProcessedHistoryFileResult(
                status="failed",
                payload=ParsedFilePayload(
                    file_name="notes.md",
                    extension=".md",
                    content_type="text/markdown",
                    size_bytes=8,
                    parsed_kind="markdown",
                    raw_text="# Notes",
                    structured_data=None,
                    row_count=None,
                    warnings=[],
                ),
                error_code="unsupported_ingest_type",
                error_message="Only CSV files are persisted in this phase.",
            ),
        ],
    )

    mock_use_case.process_files = AsyncMock(return_value=mocked_response)
    app.dependency_overrides[get_history_ingest_use_case] = lambda: mock_use_case
    try:
        response = client.post(
            "/api/ingest/history",
            files=[
                (
                    "files",
                    ("history.csv", b"question,answer,domain\nQ,A,Security\n", "text/csv"),
                ),
                (
                    "files",
                    ("notes.md", b"# Notes", "text/markdown"),
                ),
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_file_count"] == 2
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 1
    assert [item["status"] for item in payload["files"]] == ["processed", "failed"]
    assert payload["files"][1]["error_code"] == "unsupported_ingest_type"


def test_history_ingest_route_returns_422_without_any_files() -> None:
    client = TestClient(app)

    response = client.post("/api/ingest/history")

    assert response.status_code == 422
