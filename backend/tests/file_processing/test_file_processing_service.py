from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.file_processing.service import FileProcessingService


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


async def test_process_upload_parses_json_into_structured_data() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "history.json",
        b'{"hello":"world"}',
        "application/json",
    )

    result = await service.process_upload(upload)

    assert result.status == "processed"
    assert result.payload is not None
    assert result.payload.parsed_kind == "json"
    assert result.payload.structured_data == {"hello": "world"}


async def test_process_upload_parses_markdown_into_raw_text() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "policy.md",
        b"# Title\n\nPolicy body",
        "text/markdown",
    )

    result = await service.process_upload(upload)

    assert result.status == "processed"
    assert result.payload is not None
    assert result.payload.parsed_kind == "markdown"
    assert result.payload.raw_text == "# Title\n\nPolicy body"
    assert result.payload.structured_data is None


async def test_process_upload_parses_csv_into_rows() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "history.csv",
        b"name,score\nalice,9\nbob,7\n",
        "text/csv",
    )

    result = await service.process_upload(upload)

    assert result.status == "processed"
    assert result.payload is not None
    assert result.payload.parsed_kind == "csv"
    assert result.payload.structured_data == [
        {"name": "alice", "score": "9"},
        {"name": "bob", "score": "7"},
    ]
    assert result.payload.row_count == 2


async def test_process_upload_fails_for_unsupported_extension() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "history.pdf",
        b"%PDF",
        "application/pdf",
    )

    result = await service.process_upload(upload)

    assert result.status == "failed"
    assert result.payload is None
    assert result.error_code == "unsupported_extension"
