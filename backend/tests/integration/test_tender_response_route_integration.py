from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

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
    ReferenceAssessmentService,
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
        if question.question_id == "q-003":
            return HistoricalAlignmentResult(
                matched=True,
                record_id="qa-3",
                question="Describe your hosting controls.",
                answer="Regional hosting controls are available by deployment.",
                domain="Compliance",
                source_doc="historical_repository_qa.csv",
                alignment_score=0.68,
                references=[
                    HistoricalReference(
                        record_id="qa-3",
                        question="Describe your hosting controls.",
                        answer="Regional hosting controls are available by deployment.",
                        domain="Compliance",
                        source_doc="historical_repository_qa.csv",
                        alignment_score=0.68,
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
        attempt_number: int = 1,
        validation_error: str | None = None,
        last_invalid_answer: str | None = None,
        last_invalid_confidence_level: str | None = None,
        last_invalid_confidence_reason: str | None = None,
        assessment_reason: str | None = None,
    ) -> GroundedAnswerResult:
        if question.question_id == "q-003":
            return GroundedAnswerResult(
                generated_answer=(
                    "We support regional hosting controls (jurisdiction-specific "
                    "sovereign hosting guarantees are not evidenced in the retrieved "
                    "references)."
                ),
                confidence_level="medium",
                confidence_reason=(
                    "Confidence is reduced because the retrieved references support "
                    "regional hosting controls but do not evidence jurisdiction-specific "
                    "sovereign hosting guarantees or contractual commitments."
                ),
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            )
        return GroundedAnswerResult(
            generated_answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
            confidence_level="high",
            confidence_reason="Direct historical evidence supports the answer.",
            risk_level="medium",
            risk_reason="Security posture responses should still be reviewed.",
            inconsistent_response=False,
        )


class SequentialFakeAnswerGenerationService:
    def __init__(self, responses: list[GroundedAnswerResult]) -> None:
        self._responses = responses
        self.calls = 0

    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references,
        attempt_number: int = 1,
        validation_error: str | None = None,
        last_invalid_answer: str | None = None,
        last_invalid_confidence_level: str | None = None,
        last_invalid_confidence_reason: str | None = None,
        assessment_reason: str | None = None,
    ) -> GroundedAnswerResult:
        response = self._responses[self.calls]
        self.calls += 1
        return response


class FailIfCalledAnswerGenerationService:
    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references,
        attempt_number: int = 1,
        validation_error: str | None = None,
        last_invalid_answer: str | None = None,
        last_invalid_confidence_level: str | None = None,
        last_invalid_confidence_reason: str | None = None,
        assessment_reason: str | None = None,
    ) -> GroundedAnswerResult:
        raise AssertionError(
            f"answer generation should not run for conflicting references: {question.question_id}"
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
        if question.question_id == "q-003":
            return ReferenceAssessmentResult(
                can_answer=True,
                grounding_status="partial_reference",
                usable_reference_ids=["qa-3"],
                reason=(
                    "The retrieved references support hosting controls but not sovereign "
                    "guarantees."
                ),
            )
        return ReferenceAssessmentResult(
            can_answer=False,
            grounding_status="no_reference",
            usable_reference_ids=[],
            reason="No qualified historical references.",
        )


class ConflictFakeAlignmentRepository:
    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        if question.question_id != "q-013":
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
        return HistoricalAlignmentResult(
            matched=True,
            record_id="qa-18",
            question="Is legacy SSL fully disabled for all production traffic?",
            answer=(
                "Yes. Legacy SSL is fully disabled for all public and private "
                "production traffic, and only TLS 1.2 or higher is permitted in "
                "production environments."
            ),
            domain="Security",
            source_doc="historical_repository_qa.csv",
            alignment_score=0.69,
            references=[
                HistoricalReference(
                    record_id="qa-18",
                    question="Is legacy SSL fully disabled for all production traffic?",
                    answer=(
                        "Yes. Legacy SSL is fully disabled for all public and private "
                        "production traffic, and only TLS 1.2 or higher is permitted "
                        "in production environments."
                    ),
                    domain="Security",
                    source_doc="historical_repository_qa.csv",
                    alignment_score=0.69,
                ),
                HistoricalReference(
                    record_id="qa-19",
                    question=(
                        "Can legacy SSL remain enabled on selected public production "
                        "endpoints during migration windows?"
                    ),
                    answer=(
                        "Yes. Legacy SSL can remain enabled on selected public "
                        "production endpoints during managed migration windows where "
                        "a customer transition plan has been explicitly approved."
                    ),
                    domain="Security",
                    source_doc="historical_repository_qa.csv",
                    alignment_score=0.68,
                ),
            ],
        )


class FakeHistoricalEvidenceService:
    async def find_historical_evidence(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        if question.question_id != "q-020":
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
        return HistoricalAlignmentResult(
            matched=True,
            record_id="doc-1#0",
            question=None,
            answer=None,
            domain="Operations",
            source_doc="operations_playbook.txt",
            alignment_score=0.87,
            references=[
                HistoricalReference(
                    record_id="doc-1#0",
                    reference_type="document_chunk",
                    question="",
                    answer="",
                    excerpt="Quarterly recovery exercises are documented and reviewed.",
                    chunk_index=0,
                    domain="Operations",
                    source_doc="operations_playbook.txt",
                    alignment_score=0.87,
                )
            ],
        )


class UnexpectedReferenceAssessmentModel:
    def with_structured_output(self, *args, **kwargs):
        raise AssertionError(
            "structured LLM assessment should not run when conflict is detected first"
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
    assert payload["questions"][1]["confidence_level"] is None
    assert payload["questions"][1]["confidence_reason"] is None
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
    assert payload["questions"][1]["confidence_level"] is None
    assert payload["questions"][1]["confidence_reason"] is None
    assert payload["questions"][1]["references"] == []
    assert payload["summary"]["total_questions_processed"] == 2
    assert payload["summary"]["unanswered_questions"] == 1


def test_tender_response_route_returns_partial_answers_when_only_part_of_scope_is_supported() -> (
    None
):
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
                        b'q-003,Compliance,"Describe your sovereign hosting guarantees."\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-789"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_questions_processed"] == 1
    assert payload["questions"][0]["status"] == "completed"
    assert payload["questions"][0]["grounding_status"] == "partial_reference"
    assert payload["questions"][0]["confidence_level"] == "medium"
    assert "(" in payload["questions"][0]["generated_answer"]
    assert ")" in payload["questions"][0]["generated_answer"]
    assert "Confidence is reduced because" in payload["questions"][0]["confidence_reason"]
    assert "sovereign hosting guarantees" in payload["questions"][0]["confidence_reason"]


def test_tender_response_route_exposes_document_chunk_reference_metadata() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeHistoricalEvidenceService(),
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
                        b'q-020,Operations,"How often do you test disaster recovery?"\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-doc-route"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    reference = payload["questions"][0]["references"][0]
    assert reference["reference_type"] == "document_chunk"
    assert reference["excerpt"] == "Quarterly recovery exercises are documented and reviewed."
    assert reference["chunk_index"] == 0
    assert reference["matched_question"] == ""
    assert reference["matched_answer"] == ""
    assert reference["source_doc"] == "operations_playbook.txt"


def test_tender_response_route_returns_conflict_without_generating_answer() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=ConflictFakeAlignmentRepository(),
        answer_generation_service=FailIfCalledAnswerGenerationService(),
        reference_assessment_service=ReferenceAssessmentService(
            model=UnexpectedReferenceAssessmentModel()
        ),
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
                        b'q-013,Security,"Please confirm that legacy SSL is fully disabled '
                        b'for all production traffic in the proposed environment."\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-conflict-route"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    conflict = payload["questions"][0]
    assert conflict["status"] == "unanswered"
    assert conflict["grounding_status"] == "conflict"
    assert conflict["generated_answer"] is None
    assert conflict["confidence_level"] is None
    assert conflict["confidence_reason"] is None
    assert conflict["flags"]["has_conflict"] is True
    assert conflict["risk"]["level"] == "medium"
    assert "human review" in conflict["error_message"].lower()
    assert conflict["extensions"]["requires_human_review"] is True
    assert payload["summary"]["overall_completion_status"] == "conflict"
    assert payload["summary"]["unanswered_questions"] == 1
    assert payload["summary"]["conflict_count"] == 1


def test_tender_response_route_retries_invalid_partial_answer_until_second_attempt_succeeds() -> (
    None
):
    answer_service = SequentialFakeAnswerGenerationService(
        [
            GroundedAnswerResult(
                generated_answer="We support regional hosting controls.",
                confidence_level="high",
                confidence_reason="The answer is supported.",
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            ),
            GroundedAnswerResult(
                generated_answer=(
                    "We support regional hosting controls (jurisdiction-specific "
                    "sovereign hosting guarantees are not evidenced in the retrieved "
                    "references)."
                ),
                confidence_level="medium",
                confidence_reason=(
                    "Confidence is reduced because the retrieved references support "
                    "regional hosting controls but do not evidence jurisdiction-specific "
                    "sovereign hosting guarantees or contractual commitments."
                ),
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            ),
        ]
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(),
        answer_generation_service=answer_service,
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
                        b'q-003,Compliance,"Describe your sovereign hosting guarantees."\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-790"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["questions"][0]["status"] == "completed"
    assert payload["questions"][0]["grounding_status"] == "partial_reference"
    assert payload["questions"][0]["generated_answer"] is not None
    assert "(" in payload["questions"][0]["generated_answer"]
    assert ")" in payload["questions"][0]["generated_answer"]
    assert answer_service.calls == 2


def test_tender_response_route_failed_partial_answer_exposes_retry_diagnostics() -> None:
    answer_service = SequentialFakeAnswerGenerationService(
        [
            GroundedAnswerResult(
                generated_answer="We support regional hosting controls.",
                confidence_level="high",
                confidence_reason="The answer is supported.",
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            ),
            GroundedAnswerResult(
                generated_answer="We support regional hosting controls.",
                confidence_level="high",
                confidence_reason="The answer is supported.",
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            ),
            GroundedAnswerResult(
                generated_answer="We support regional hosting controls.",
                confidence_level="high",
                confidence_reason="The answer is supported.",
                risk_level="medium",
                risk_reason="Human review is required before making hosting commitments.",
                inconsistent_response=False,
            ),
        ]
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(),
        answer_generation_service=answer_service,
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
                        b'q-003,Compliance,"Describe your sovereign hosting guarantees."\n'
                    ),
                    "text/csv",
                )
            },
            data={"sessionId": "session-791"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    failed = payload["questions"][0]
    assert failed["status"] == "failed"
    assert failed["grounding_status"] == "failed"
    assert failed["error_message"] == "Partial answer must identify missing scope in parentheses."
    assert (
        failed["extensions"]["reference_assessment_reason"]
        == "The retrieved references support hosting controls but not sovereign guarantees."
    )
    assert failed["extensions"]["generation_attempt_count"] == 3
    assert failed["extensions"]["generation_retry_history"] == [
        "Partial answer must identify missing scope in parentheses.",
        "Partial answer must identify missing scope in parentheses.",
        "Partial answer must identify missing scope in parentheses.",
    ]
    assert failed["extensions"]["last_invalid_answer"] == "We support regional hosting controls."
    assert failed["extensions"]["last_invalid_confidence_level"] == "high"
    assert failed["extensions"]["last_invalid_confidence_reason"] == "The answer is supported."
    assert answer_service.calls == 3
