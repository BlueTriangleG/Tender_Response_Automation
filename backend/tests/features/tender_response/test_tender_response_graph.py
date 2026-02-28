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


class FakeAlignmentRepository:
    def __init__(self, results: dict[str, HistoricalAlignmentResult]) -> None:
        self.results = results

    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        return self.results[question.question_id]


class FakeAnswerGenerationService:
    def __init__(self) -> None:
        self.with_alignment_calls: list[str] = []
        self.without_alignment_calls: list[str] = []

    async def generate_with_alignment(
        self,
        *,
        question: TenderQuestion,
        alignment: HistoricalAlignmentResult,
    ) -> str:
        self.with_alignment_calls.append(question.question_id)
        if question.question_id == "q-003":
            raise RuntimeError("generation failed")
        return f"Aligned answer for {question.question_id}"

    async def generate_without_alignment(self, question: TenderQuestion) -> str:
        self.without_alignment_calls.append(question.question_id)
        if question.question_id == "q-004":
            return "Yes, we are FedRAMP authorised."
        return f"Conservative answer for {question.question_id}"


async def test_tender_response_graph_processes_any_number_of_questions() -> None:
    answer_service = FakeAnswerGenerationService()
    workflow = create_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-001": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-1",
                    question="Historical TLS question",
                    answer="Historical TLS answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.95,
                ),
                "q-002": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.41,
                ),
            }
        ),
        answer_generation_service=answer_service,
        domain_tagging_service=DomainTaggingService(),
        confidence_service=ConfidenceService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-1",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-001",
                    original_question="Do you support TLS 1.2 or above?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
                TenderQuestion(
                    question_id="q-002",
                    original_question="Are you FedRAMP authorised?",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=1,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
            "current_alignment": None,
            "current_answer": None,
            "current_result": None,
        },
        config={"configurable": {"thread_id": "session-1"}},
    )

    assert len(result["question_results"]) == 2
    assert answer_service.with_alignment_calls == ["q-001"]
    assert answer_service.without_alignment_calls == ["q-002"]
    assert result["question_results"][0].reference is not None
    assert result["question_results"][0].reference.source_doc == "history.csv"
    assert result["question_results"][1].reference is None
    assert result["summary"].total_questions_processed == 2


async def test_tender_response_graph_keeps_processing_when_one_question_fails() -> None:
    workflow = create_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-001": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-1",
                    question="Historical TLS question",
                    answer="Historical TLS answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.95,
                ),
                "q-003": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-2",
                    question="Historical SSO question",
                    answer="Historical SSO answer",
                    domain="Architecture",
                    source_doc="history.csv",
                    alignment_score=0.94,
                ),
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        domain_tagging_service=DomainTaggingService(),
        confidence_service=ConfidenceService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-2",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-001",
                    original_question="Do you support TLS 1.2 or above?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
                TenderQuestion(
                    question_id="q-003",
                    original_question="Do you support SAML SSO?",
                    declared_domain="Architecture",
                    source_file_name="tender.csv",
                    source_row_index=1,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
            "current_alignment": None,
            "current_answer": None,
            "current_result": None,
        },
        config={"configurable": {"thread_id": "session-2"}},
    )

    statuses = {item.question_id: item.status for item in result["question_results"]}
    assert statuses["q-001"] == "completed"
    assert statuses["q-003"] == "failed"
    assert result["summary"].overall_completion_status == "partial_failure"


async def test_tender_response_graph_marks_flagged_responses_in_summary() -> None:
    workflow = create_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-004": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.35,
                ),
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        domain_tagging_service=DomainTaggingService(),
        confidence_service=ConfidenceService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-3",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-004",
                    original_question="Are you FedRAMP authorised?",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
            "current_alignment": None,
            "current_answer": None,
            "current_result": None,
        },
        config={"configurable": {"thread_id": "session-3"}},
    )

    assert result["question_results"][0].flags.high_risk is True
    assert result["summary"].flagged_high_risk_or_inconsistent_responses == 1
    assert result["summary"].overall_completion_status == "completed_with_flags"
