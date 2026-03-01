from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from xml.sax.saxutils import escape

from app.features.tender_response.api.dependencies import get_tender_response_runner
from app.features.tender_response.application.tender_response_runner import (
    TenderResponseRunner,
)
from app.features.tender_response.domain.models import (
    GroundedAnswerResult,
    HistoricalAlignmentResult,
    HistoricalReference,
    TenderQuestion,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentResult,
)
from app.features.tender_response.infrastructure.workflows.parallel.graph import (
    create_parallel_tender_response_graph,
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
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
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


class FakeAlignmentRepository:
    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        if question.question_id == "q-001":
            return HistoricalAlignmentResult(
                matched=True,
                record_id="qa-1",
                question="Historical TLS question",
                answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                domain="Security",
                source_doc="historical_repository_qa.csv",
                alignment_score=0.95,
                references=[
                    HistoricalReference(
                        record_id="qa-1",
                        question="Historical TLS question",
                        answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                        domain="Security",
                        source_doc="historical_repository_qa.csv",
                        alignment_score=0.95,
                    )
                ],
            )
        return HistoricalAlignmentResult(
            matched=False,
            record_id=None,
            question=None,
            answer=None,
            domain=None,
            source_doc=None,
            alignment_score=0.35,
            references=[],
        )


class FakeAnswerGenerationService:
    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references,
    ) -> GroundedAnswerResult:
        return GroundedAnswerResult(
            generated_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
            confidence_level="high",
            confidence_reason="Direct historical evidence supports the answer.",
            risk_level="medium",
            risk_reason="Security posture responses should still be reviewed.",
            inconsistent_response=False,
        )


class FakeReferenceAssessmentService:
    async def assess(self, *, question: TenderQuestion, references):
        if question.question_id == "q-001":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="grounded",
                usable_reference_ids=["qa-1"],
                reason="Historical answer is sufficient.",
            )
        return ReferenceAssessmentResult(
            can_answer=False,
            grounding_status="no_reference",
            usable_reference_ids=[],
            reason="No qualified historical references.",
        )


def test_tender_response_route_processes_csv_end_to_end_with_fake_workflow_services() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(),
        domain_tagging_service=DomainTaggingService(),
    )
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]
    client = TestClient(app)

    app.dependency_overrides[get_tender_response_runner] = lambda: runner
    try:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    "tender.csv",
                    (
                        b"question_id,domain,question\n"
                        b'q-001,Security,"Do you support TLS 1.2 or above?"\n'
                        b'q-002,Compliance,"Are you FedRAMP authorised?"\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-456"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_questions_processed"] == 2
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["references"][0]["matched_question"] == "Historical TLS question"
    assert payload["questions"][0]["references"][0]["source_doc"] == "historical_repository_qa.csv"
    assert payload["questions"][0]["grounding_status"] == "grounded"
    assert payload["questions"][0]["confidence_level"] == "high"
    assert payload["questions"][0]["risk"]["level"] == "medium"
    assert payload["questions"][1]["generated_answer"] is None
    assert payload["questions"][1]["status"] == "unanswered"
    assert payload["questions"][1]["grounding_status"] == "no_reference"
    assert payload["questions"][1]["references"] == []
    assert payload["summary"]["total_questions_processed"] == 2
    assert payload["summary"]["unanswered_questions"] == 1


def test_tender_response_route_processes_xlsx_end_to_end_with_fake_workflow_services() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(),
        domain_tagging_service=DomainTaggingService(),
    )
    runner = TenderResponseRunner()
    runner._workflow_registry.get = lambda workflow_name: workflow  # type: ignore[attr-defined]
    client = TestClient(app)

    app.dependency_overrides[get_tender_response_runner] = lambda: runner
    try:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    "tender.xlsx",
                    build_workbook_bytes(
                        [
                            ["question_id", "domain", "question"],
                            ["q-001", "Security", "Do you support TLS 1.2 or above?"],
                            ["q-002", "Compliance", "Are you FedRAMP authorised?"],
                        ]
                    ),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"sessionId": "session-456"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_file_name"] == "tender.xlsx"
    assert payload["total_questions_processed"] == 2
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["references"][0]["matched_question"] == "Historical TLS question"
    assert payload["questions"][0]["references"][0]["source_doc"] == "historical_repository_qa.csv"
    assert payload["questions"][0]["grounding_status"] == "grounded"
    assert payload["questions"][0]["confidence_level"] == "high"
    assert payload["questions"][0]["risk"]["level"] == "medium"
    assert payload["questions"][1]["generated_answer"] is None
    assert payload["questions"][1]["status"] == "unanswered"
    assert payload["questions"][1]["grounding_status"] == "no_reference"
    assert payload["questions"][1]["references"] == []
    assert payload["summary"]["total_questions_processed"] == 2
    assert payload["summary"]["unanswered_questions"] == 1
