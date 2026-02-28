from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)
from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions


def make_upload_file(
    filename: str,
    content: bytes,
    content_type: str,
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


async def test_process_files_marks_non_csv_upload_as_failed_ingest_type() -> None:
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file(
                "history.json",
                b'{"hello":"world"}',
                "application/json",
            )
        ],
        request_options=HistoryIngestRequestOptions(
            output_format="excel",
            similarity_threshold=0.84,
        ),
    )

    assert response.total_file_count == 1
    assert response.processed_file_count == 0
    assert response.failed_file_count == 1
    assert response.request_options.output_format == "excel"
    assert response.request_options.similarity_threshold == 0.84
    assert response.files[0].status == "failed"
    assert response.files[0].error_code == "unsupported_ingest_type"


async def test_process_files_marks_non_csv_uploads_as_failed_individually() -> None:
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file("one.md", b"# one", "text/markdown"),
            make_upload_file("three.json", b'{"ok":true}', "application/json"),
        ]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 0
    assert response.failed_file_count == 2
    assert [result.status for result in response.files] == [
        "failed",
        "failed",
    ]
    assert response.files[0].error_code == "unsupported_ingest_type"
    assert response.files[1].error_code == "unsupported_ingest_type"


async def test_process_files_continues_when_one_file_fails() -> None:
    service = IngestHistoryUseCase()

    response = await service.process_files(
        [
            make_upload_file("bad.pdf", b"%PDF", "application/pdf"),
            make_upload_file("good.md", b"# ok", "text/markdown"),
        ]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 0
    assert response.failed_file_count == 2
    assert response.files[0].status == "failed"
    assert response.files[0].error_code == "unsupported_extension"
    assert response.files[1].status == "failed"
    assert response.files[1].error_code == "unsupported_ingest_type"
