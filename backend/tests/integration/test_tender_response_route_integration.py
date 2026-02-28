from fastapi.testclient import TestClient

from app.features.tender_response.api.dependencies import get_process_tender_csv_use_case
from app.features.tender_response.application.process_tender_csv_use_case import (
    ProcessTenderCsvUseCase,
)
from app.features.tender_response.domain.models import HistoricalAlignmentResult, TenderQuestion
from app.features.tender_response.infrastructure.services.confidence_service import (
    ConfidenceService,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.infrastructure.workflows.tender_response_graph import (
    create_tender_response_graph,
)
from app.main import app


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
                alignment_score=0.95,
            )
        return HistoricalAlignmentResult(
            matched=False,
            record_id=None,
            question=None,
            answer=None,
            domain=None,
            alignment_score=0.35,
        )


class FakeAnswerGenerationService:
    async def generate_with_alignment(
        self,
        *,
        question: TenderQuestion,
        alignment: HistoricalAlignmentResult,
    ) -> str:
        return "Yes. Production traffic is restricted to TLS 1.2 or higher."

    async def generate_without_alignment(self, question: TenderQuestion) -> str:
        return "Based on the available information, this answer cannot be fully confirmed."


def test_tender_response_route_processes_csv_end_to_end_with_fake_workflow_services() -> None:
    workflow = create_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(),
        answer_generation_service=FakeAnswerGenerationService(),
        domain_tagging_service=DomainTaggingService(),
        confidence_service=ConfidenceService(),
    )
    use_case = ProcessTenderCsvUseCase(workflow=workflow)
    client = TestClient(app)

    app.dependency_overrides[get_process_tender_csv_use_case] = lambda: use_case
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
    assert payload["summary"]["total_questions_processed"] == 2
