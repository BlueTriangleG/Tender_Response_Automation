from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.features.tender_response.api.dependencies import get_tender_response_runner
from app.features.tender_response.application.tender_response_runner import (
    TenderResponseRunner,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
    TenderResponseWorkflowResponse,
)
from app.main import app


def build_workbook_bytes(rows: list[list[str]]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        archive.writestr("_rels/.rels", ROOT_RELS_XML)
        archive.writestr("xl/workbook.xml", WORKBOOK_XML)
        archive.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS_XML)
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(rows))
    return buffer.getvalue()


CONTENT_TYPES_XML = (
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
)

ROOT_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/>'
    "</Relationships>"
)

WORKBOOK_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Tender Questions" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)

WORKBOOK_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
    'Target="worksheets/sheet1.xml"/>'
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


class FakeWorkflow:
    async def ainvoke(self, state: dict, config: dict) -> dict:
        return {
            "question_results": [
                TenderQuestionResponse(
                    question_id="q-001",
                    original_question=state["questions"][0].original_question,
                    generated_answer="Yes.",
                    domain_tag="security",
                    confidence_level="high",
                    confidence_reason="Direct historical evidence supports the answer.",
                    historical_alignment_indicator=True,
                    status="completed",
                    grounding_status="grounded",
                    flags=QuestionFlags(high_risk=False, inconsistent_response=False),
                    risk=QuestionRisk(
                        level="medium",
                        reason="Security posture responses should still be reviewed.",
                    ),
                    metadata=QuestionMetadata(
                        source_row_index=0,
                        alignment_record_id="qa-1",
                        alignment_score=0.92,
                    ),
                    references=[
                        QuestionReference(
                            alignment_record_id="qa-1",
                            alignment_score=0.92,
                            source_doc="historical_repository_qa.csv",
                            matched_question="Do you support TLS 1.2 or above?",
                            matched_answer="Yes.",
                            used_for_answer=True,
                        )
                    ],
                    error_message=None,
                    extensions={},
                )
            ],
            "summary": TenderResponseSummary(
                total_questions_processed=1,
                flagged_high_risk_or_inconsistent_responses=0,
                overall_completion_status="completed",
                completed_questions=1,
                unanswered_questions=0,
                failed_questions=0,
            ),
        }


def test_tender_response_route_accepts_csv_upload_and_returns_json() -> None:
    client = TestClient(app)
    mock_runner = MagicMock()
    mock_runner.process_upload = AsyncMock(
        return_value=TenderResponseWorkflowResponse(
            request_id="req-123",
            session_id="session-123",
            source_file_name="tender.csv",
            total_questions_processed=1,
            questions=[
                TenderQuestionResponse(
                    question_id="q-001",
                    original_question="Do you support TLS 1.2 or above?",
                    generated_answer="Yes.",
                    domain_tag="security",
                    confidence_level="high",
                    confidence_reason="Direct historical evidence supports the answer.",
                    historical_alignment_indicator=True,
                    status="completed",
                    grounding_status="grounded",
                    flags=QuestionFlags(high_risk=False, inconsistent_response=False),
                    risk=QuestionRisk(
                        level="medium",
                        reason="Security posture responses should still be reviewed.",
                    ),
                    metadata=QuestionMetadata(
                        source_row_index=0,
                        alignment_record_id="qa-1",
                        alignment_score=0.92,
                    ),
                    references=[
                        QuestionReference(
                            alignment_record_id="qa-1",
                            alignment_score=0.92,
                            source_doc="historical_repository_qa.csv",
                            matched_question="Do you support TLS 1.2 or above?",
                            matched_answer="Yes.",
                            used_for_answer=True,
                        )
                    ],
                    error_message=None,
                    extensions={},
                )
            ],
            summary=TenderResponseSummary(
                total_questions_processed=1,
                flagged_high_risk_or_inconsistent_responses=0,
                overall_completion_status="completed",
                completed_questions=1,
                unanswered_questions=0,
                failed_questions=0,
            ),
        )
    )

    app.dependency_overrides[get_tender_response_runner] = lambda: mock_runner
    try:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    "tender.csv",
                    b'question_id,question\nq-001,"Do you support TLS 1.2 or above?"\n',
                    "text/csv",
                )
            },
            data={"sessionId": "session-123", "alignmentThreshold": "0.84"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_questions_processed"] == 1
    assert payload["questions"][0]["generated_answer"] == "Yes."
    assert payload["questions"][0]["confidence_reason"] is not None
    assert payload["questions"][0]["risk"]["level"] == "medium"
    assert payload["questions"][0]["references"][0]["source_doc"] == "historical_repository_qa.csv"
    assert payload["summary"]["overall_completion_status"] == "completed"


def test_tender_response_route_accepts_xlsx_upload_and_returns_json() -> None:
    client = TestClient(app)
    runner = TenderResponseRunner()
    # type: ignore[attr-defined]
    runner._workflow_registry.get = lambda workflow_name: FakeWorkflow()

    app.dependency_overrides[get_tender_response_runner] = lambda: runner
    try:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    "tender.xlsx",
                    build_workbook_bytes(
                        [
                            ["question_id", "question"],
                            ["q-001", "Do you support TLS 1.2 or above?"],
                        ]
                    ),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"sessionId": "session-123", "alignmentThreshold": "0.84"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_file_name"] == "tender.xlsx"
    assert payload["total_questions_processed"] == 1
    assert payload["questions"][0]["generated_answer"] == "Yes."
    assert payload["summary"]["overall_completion_status"] == "completed"


def test_tender_response_route_rejects_non_csv_upload() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/tender/respond",
        files={"file": ("tender.md", b"# nope", "text/markdown")},
    )

    assert response.status_code == 400
