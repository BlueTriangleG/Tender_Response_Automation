from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.schemas.history_ingest import HistoryIngestRequestOptions
from app.services.history_ingest_service import HistoryIngestService


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


async def test_process_files_handles_one_uploaded_file() -> None:
    service = HistoryIngestService()

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
    assert response.processed_file_count == 1
    assert response.failed_file_count == 0
    assert response.request_options.output_format == "excel"
    assert response.request_options.similarity_threshold == 0.84
    assert response.files[0].status == "processed"


async def test_process_files_handles_many_uploaded_files() -> None:
    service = HistoryIngestService()

    response = await service.process_files(
        [
            make_upload_file("one.md", b"# one", "text/markdown"),
            make_upload_file("two.csv", b"name\nalice\n", "text/csv"),
            make_upload_file("three.json", b'{"ok":true}', "application/json"),
        ]
    )

    assert response.total_file_count == 3
    assert response.processed_file_count == 3
    assert response.failed_file_count == 0
    assert [result.status for result in response.files] == [
        "processed",
        "processed",
        "processed",
    ]


async def test_process_files_continues_when_one_file_fails() -> None:
    service = HistoryIngestService()

    response = await service.process_files(
        [
            make_upload_file("bad.pdf", b"%PDF", "application/pdf"),
            make_upload_file("good.md", b"# ok", "text/markdown"),
        ]
    )

    assert response.total_file_count == 2
    assert response.processed_file_count == 1
    assert response.failed_file_count == 1
    assert response.files[0].status == "failed"
    assert response.files[1].status == "processed"
