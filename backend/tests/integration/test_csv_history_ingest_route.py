from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.lancedb_client import get_lancedb_connection
from app.main import app


async def fake_embed_texts(self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


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
                "Type="
                '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                'officeDocument" '
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
                "Type="
                '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
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


def test_csv_history_ingest_route_persists_rows_to_qa_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/ingest/history",
            files={
                "file": (
                    "history.csv",
                    b"question,answer,domain\nWhat is TLS?,TLS 1.2+,Security\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 0
    assert payload["files"][0]["ingested_row_count"] == 1
    assert payload["files"][0]["storage_target"] == "qa_records"

    connection = get_lancedb_connection(db_uri)
    table = connection.open_table(settings.lancedb_qa_table_name)
    rows = table.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["question"] == "What is TLS?"
    assert rows[0]["answer"] == "TLS 1.2+"
    assert rows[0]["domain"] == "Security"


def test_xlsx_history_ingest_route_persists_rows_to_qa_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )

    workbook_bytes = build_workbook_bytes(
        [
            ["question", "answer", "domain"],
            ["Do you support TLS 1.2 or higher?", "Yes", "Security"],
        ]
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/ingest/history",
            files={
                "file": (
                    "history.xlsx",
                    workbook_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 0
    assert payload["files"][0]["ingested_row_count"] == 1
    assert payload["files"][0]["storage_target"] == "qa_records"

    connection = get_lancedb_connection(db_uri)
    table = connection.open_table(settings.lancedb_qa_table_name)
    rows = table.to_arrow().to_pylist()

    assert len(rows) == 1
    assert rows[0]["question"] == "Do you support TLS 1.2 or higher?"
    assert rows[0]["answer"] == "Yes"
    assert rows[0]["domain"] == "Security"


def test_history_ingest_route_supports_mixed_tabular_and_document_batches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_uri = tmp_path / "lancedb"
    monkeypatch.setattr(settings, "lancedb_uri", str(db_uri))
    monkeypatch.setattr(
        "app.features.history_ingest.infrastructure.services.qa_embedding_service.QaEmbeddingService.embed_texts",
        fake_embed_texts,
    )

    workbook_bytes = build_workbook_bytes(
        [
            ["question", "answer", "domain"],
            ["Do you support SSO?", "Yes", "Security"],
        ]
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/ingest/history",
            files=[
                (
                    "files",
                    (
                        "history.csv",
                        b"question,answer,domain\nWhat is TLS?,TLS 1.2+,Security\n",
                        "text/csv",
                    ),
                ),
                (
                    "files",
                    (
                        "history.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                (
                    "files",
                    (
                        "operations.md",
                        b"# Operations\n\nPeer review is required.\n",
                        "text/markdown",
                    ),
                ),
                (
                    "files",
                    ("operations.txt", b"Escalate incidents within 30 minutes.\n", "text/plain"),
                ),
            ],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_file_count"] == 4
    assert payload["failed_file_count"] == 0
    assert [file["storage_target"] for file in payload["files"]] == [
        "qa_records",
        "qa_records",
        "document_records",
        "document_records",
    ]

    connection = get_lancedb_connection(db_uri)
    qa_rows = connection.open_table(settings.lancedb_qa_table_name).to_arrow().to_pylist()
    document_rows = (
        connection.open_table(settings.lancedb_document_table_name).to_arrow().to_pylist()
    )

    assert len(qa_rows) == 2
    assert len(document_rows) == 2
