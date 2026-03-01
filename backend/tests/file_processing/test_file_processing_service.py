from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from xml.sax.saxutils import escape

from starlette.datastructures import Headers, UploadFile

from app.features.history_ingest.infrastructure.file_processing_service import (
    FileProcessingService,
)


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


def build_workbook_bytes(rows: list[list[str]]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="History" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(rows))
    return buffer.getvalue()


def build_sheet_xml(rows: list[list[str]]) -> str:
    row_xml = "".join(
        f'<row r="{row_index}">{build_cell_xml(row_index, row)}</row>'
        for row_index, row in enumerate(rows, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{row_xml}</sheetData>"
        "</worksheet>"
    )


def build_cell_xml(row_index: int, row: list[str]) -> str:
    return "".join(
        (
            f'<c r="{column_letter(column_index)}{row_index}" t="inlineStr">'
            f"<is><t>{escape(value)}</t></is>"
            "</c>"
        )
        for column_index, value in enumerate(row, start=1)
    )


def column_letter(column_index: int) -> str:
    result = ""
    index = column_index
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


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


async def test_process_upload_parses_text_into_raw_text() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "history.txt",
        b"Operations runbook\nRotate credentials every 90 days.\n",
        "text/plain",
    )

    result = await service.process_upload(upload)

    assert result.status == "processed"
    assert result.payload is not None
    assert result.payload.parsed_kind == "text"
    assert result.payload.raw_text == "Operations runbook\nRotate credentials every 90 days.\n"
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


async def test_process_upload_parses_xlsx_into_rows() -> None:
    service = FileProcessingService()
    upload = make_upload_file(
        "history.xlsx",
        build_workbook_bytes(
            [
                ["question", "answer", "domain"],
                ["Do you support TLS 1.2 or higher?", "Yes", "Security"],
                ["Do you support SCIM?", "Yes", "Identity"],
            ]
        ),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    result = await service.process_upload(upload)

    assert result.status == "processed"
    assert result.payload is not None
    assert result.payload.parsed_kind == "spreadsheet"
    assert result.payload.structured_data == [
        {
            "question": "Do you support TLS 1.2 or higher?",
            "answer": "Yes",
            "domain": "Security",
        },
        {
            "question": "Do you support SCIM?",
            "answer": "Yes",
            "domain": "Identity",
        },
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
