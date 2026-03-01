from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from starlette.datastructures import Headers, UploadFile

from app.core.config import settings
from app.features.tender_response.application.tender_response_runner import (
    TenderResponseRunner,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionReference,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
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
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.configs: list[dict] = []
        self.state_values: dict = {}

    async def aget_state(self, config: dict):
        self.configs.append({"state_lookup": config})

        class Snapshot:
            def __init__(self, values: dict) -> None:
                self.values = values

        return Snapshot(self.state_values)

    async def ainvoke(self, state: dict, config: dict) -> dict:
        self.calls.append(state)
        self.configs.append(config)
        return {
            "question_results": [
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
                            source_doc="history.csv",
                            matched_question="Historical TLS question",
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


async def test_process_upload_parses_csv_and_invokes_workflow() -> None:
    workflow = FakeWorkflow()
    previous_completed = TenderQuestionResponse(
        question_id="q-000",
        original_question="Do you support SAML SSO?",
        generated_answer="Yes. SAML SSO is supported.",
        domain_tag="architecture",
        confidence_level="high",
        confidence_reason="Historical references directly support the response.",
        historical_alignment_indicator=True,
        status="completed",
        grounding_status="grounded",
        flags=QuestionFlags(high_risk=False, inconsistent_response=False),
        risk=QuestionRisk(level="low", reason="Low risk."),
        metadata=QuestionMetadata(
            source_row_index=0,
            alignment_record_id="qa-0",
            alignment_score=0.93,
        ),
        references=[],
        error_message=None,
        extensions={},
    )
    workflow.state_values = {"session_completed_results": [previous_completed]}
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]

    result = await runner.process_upload(
        make_upload_file(
            "tender.csv",
            b'question_id,question\nq-001,"Do you support TLS 1.2 or above?"\n',
            "text/csv",
        ),
        TenderResponseRequestOptions(session_id="session-123", alignment_threshold=0.84),
        workflow_name="parallel",
    )

    assert result.source_file_name == "tender.csv"
    assert result.total_questions_processed == 1
    assert result.questions[0].generated_answer == "Yes."
    assert workflow.calls[0]["questions"][0].question_id == "q-001"
    assert workflow.calls[0]["session_completed_results"] == [previous_completed]
    assert workflow.calls[0]["request_id"] == result.request_id
    assert workflow.configs[0] == {"state_lookup": {"configurable": {"thread_id": "session-123"}}}
    assert workflow.configs[1] == {"configurable": {"thread_id": "session-123"}}


async def test_process_upload_accepts_xlsx_and_invokes_workflow() -> None:
    workflow = FakeWorkflow()
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]

    result = await runner.process_upload(
        make_upload_file(
            "tender.xlsx",
            build_workbook_bytes(
                [
                    ["question_id", "question"],
                    ["q-001", "Do you support TLS 1.2 or above?"],
                ]
            ),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        TenderResponseRequestOptions(session_id="session-123", alignment_threshold=0.84),
        workflow_name="parallel",
    )

    assert result.source_file_name == "tender.xlsx"
    assert result.total_questions_processed == 1
    assert result.questions[0].generated_answer == "Yes."
    assert workflow.calls[0]["questions"][0].question_id == "q-001"
    assert workflow.calls[0]["request_id"] == result.request_id
    assert workflow.configs[1] == {"configurable": {"thread_id": "session-123"}}


async def test_process_upload_falls_back_to_request_id_when_session_id_is_missing() -> None:
    workflow = FakeWorkflow()
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]

    result = await runner.process_upload(
        make_upload_file(
            "tender.csv",
            b'question_id,question\nq-001,"Do you support TLS 1.2 or above?"\n',
            "text/csv",
        ),
        TenderResponseRequestOptions(alignment_threshold=0.84),
        workflow_name="parallel",
    )

    assert workflow.calls[0]["session_completed_results"] == []
    assert workflow.configs[0] == {
        "state_lookup": {"configurable": {"thread_id": result.request_id}}
    }
    assert workflow.configs[1] == {"configurable": {"thread_id": result.request_id}}


async def test_process_upload_rejects_non_csv_files() -> None:
    runner = TenderResponseRunner()

    try:
        await runner.process_upload(
            make_upload_file("tender.md", b"# nope", "text/markdown"),
            TenderResponseRequestOptions(session_id="session-123"),
            workflow_name="parallel",
        )
    except ValueError as exc:
        assert "csv" in str(exc).lower()
    else:
        raise AssertionError("Expected use case to reject non-CSV files")


async def test_process_upload_rejects_malformed_xlsx_files() -> None:
    runner = TenderResponseRunner()

    try:
        await runner.process_upload(
            make_upload_file(
                "tender.xlsx",
                b"not a real workbook",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            TenderResponseRequestOptions(session_id="session-123"),
            workflow_name="parallel",
        )
    except ValueError as exc:
        assert "xlsx" in str(exc).lower()
    else:
        raise AssertionError("Expected use case to reject malformed XLSX files")


async def test_process_upload_prints_debug_timing_when_enabled(
    monkeypatch,
    capsys,
) -> None:
    workflow = FakeWorkflow()
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]
    monkeypatch.setattr(settings, "tender_workflow_debug", True)

    try:
        await runner.process_upload(
            make_upload_file(
                "tender.csv",
                b'question_id,question\nq-001,"Do you support TLS 1.2 or above?"\n',
                "text/csv",
            ),
            TenderResponseRequestOptions(session_id="session-123", alignment_threshold=0.5),
            workflow_name="parallel",
        )
    finally:
        monkeypatch.setattr(settings, "tender_workflow_debug", False)

    captured = capsys.readouterr()
    assert "[tender_response]" in captured.out
    assert "workflow completed" in captured.out
