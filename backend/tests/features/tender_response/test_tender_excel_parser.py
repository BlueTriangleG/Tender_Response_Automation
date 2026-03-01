from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from xml.sax.saxutils import escape


def build_workbook_bytes(
    rows: list[list[str]],
    *,
    hidden_rows: list[list[str]] | None = None,
    hidden_state: str = "hidden",
    absolute_targets: bool = False,
) -> bytes:
    sheets = [("Tender Questions", rows, None)]
    if hidden_rows is not None:
        sheets.insert(0, ("Archive", hidden_rows, hidden_state))

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", build_content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", ROOT_RELS_XML)
        archive.writestr("xl/workbook.xml", build_workbook_xml(sheets))
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            build_workbook_rels_xml(len(sheets), absolute_targets=absolute_targets),
        )
        for index, (_, sheet_rows, _) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", build_sheet_xml(sheet_rows))

    return buffer.getvalue()


def build_content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{sheet_overrides}"
        "</Types>"
    )


ROOT_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/>'
    "</Relationships>"
)


def build_workbook_xml(sheets: list[tuple[str, list[list[str]], str | None]]) -> str:
    sheet_entries = "".join(
        build_sheet_entry(name=name, index=index, hidden=hidden)
        for index, (name, _, hidden) in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_entries}</sheets>"
        "</workbook>"
    )


def build_sheet_entry(*, name: str, index: int, hidden: str | None) -> str:
    hidden_attr = f' state="{hidden}"' if hidden else ""
    return f'<sheet name="{escape(name)}" sheetId="{index}"{hidden_attr} r:id="rId{index}"/>'


def build_workbook_rels_xml(sheet_count: int, *, absolute_targets: bool = False) -> str:
    relationships = "".join(
        (
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="{"/xl/worksheets" if absolute_targets else "worksheets"}/sheet{index}.xml"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}"
        "</Relationships>"
    )


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


def build_parser():
    from app.features.tender_response.infrastructure.parsers.tender_excel_parser import (
        TenderExcelParser,
    )

    return TenderExcelParser()


def test_tender_excel_parser_extracts_questions_from_first_visible_sheet() -> None:
    parser = build_parser()

    result = parser.parse_bytes(
        build_workbook_bytes(
            [
                ["question_id", "domain", "question"],
                ["q-001", "Security", "Do you support TLS 1.2 or higher?"],
                ["q-ignored", "Security", "   "],
                ["", "Identity", "Do you support SCIM provisioning?"],
            ],
            hidden_rows=[
                ["question_id", "question"],
                ["q-hidden", "Should not be parsed"],
            ],
        ),
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 2
    assert result.questions[0].question_id == "q-001"
    assert result.questions[0].declared_domain == "Security"
    assert result.questions[1].question_id == "row-3"
    assert result.questions[1].source_row_index == 2


def test_tender_excel_parser_supports_absolute_worksheet_targets() -> None:
    parser = build_parser()

    result = parser.parse_bytes(
        build_workbook_bytes(
            [
                ["question_id", "domain", "question"],
                ["q-001", "Security", "Do you support TLS 1.2 or higher?"],
            ],
            absolute_targets=True,
        ),
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 1
    assert result.questions[0].question_id == "q-001"


def test_tender_excel_parser_uses_first_non_empty_row_as_headers() -> None:
    parser = build_parser()

    result = parser.parse_bytes(
        build_workbook_bytes(
            [
                ["", "", ""],
                ["question_id", "domain", "question"],
                ["q-001", "Security", "Do you support TLS 1.2 or higher?"],
            ]
        ),
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 1
    assert result.questions[0].question_id == "q-001"
    assert result.questions[0].declared_domain == "Security"
    assert result.questions[0].original_question == "Do you support TLS 1.2 or higher?"


def test_tender_excel_parser_skips_very_hidden_sheets() -> None:
    parser = build_parser()

    result = parser.parse_bytes(
        build_workbook_bytes(
            [
                ["question_id", "question"],
                ["q-001", "Do you support TLS 1.2 or higher?"],
            ],
            hidden_rows=[
                ["question_id", "question"],
                ["q-hidden", "Should not be parsed"],
            ],
            hidden_state="veryHidden",
        ),
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 1
    assert result.questions[0].question_id == "q-001"


def test_tender_excel_parser_rejects_workbook_without_question_column() -> None:
    parser = build_parser()

    try:
        parser.parse_bytes(
            build_workbook_bytes(
                [
                    ["domain", "client_priority"],
                    ["Security", "High"],
                ]
            ),
            source_file_name="tender.xlsx",
        )
    except ValueError as exc:
        assert "question column" in str(exc).lower()
    else:
        raise AssertionError("Expected parser to reject workbook without a question column")


def test_tender_excel_parser_rejects_malformed_xlsx_bytes() -> None:
    parser = build_parser()

    try:
        parser.parse_bytes(b"not a zip", source_file_name="tender.xlsx")
    except ValueError as exc:
        assert "xlsx" in str(exc).lower()
    else:
        raise AssertionError("Expected parser to reject malformed xlsx bytes")
