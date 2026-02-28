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
        self.answer_calls: list[str] = []

    async def generate_grounded_response(
        self,
        *,
        question: TenderQuestion,
        usable_references,
    ) -> GroundedAnswerResult:
        self.answer_calls.append(question.question_id)
        if question.question_id == "q-003":
            raise RuntimeError("generation failed")
        return GroundedAnswerResult(
            generated_answer=f"Aligned answer for {question.question_id}",
            confidence_level="high",
            confidence_reason="Direct historical evidence supports the answer.",
            risk_level="medium",
            risk_reason="Security response should still be reviewed.",
            inconsistent_response=False,
        )


class FakeReferenceAssessmentService:
    def __init__(self, results: dict[str, ReferenceAssessmentResult]) -> None:
        self.results = results

    async def assess(self, *, question: TenderQuestion, references):
        return self.results[question.question_id]


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
                    references=[
                        HistoricalReference(
                            record_id="qa-1",
                            question="Historical TLS question",
                            answer="Historical TLS answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.95,
                        )
                    ],
                ),
                "q-002": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.41,
                    references=[],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-001": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-1"],
                    reason="Historical answer is sufficient.",
                ),
                "q-002": ReferenceAssessmentResult(
                    can_answer=False,
                    grounding_status="no_reference",
                    usable_reference_ids=[],
                    reason="No qualified historical references.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
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
    assert answer_service.answer_calls == ["q-001"]
    assert result["question_results"][0].references[0].source_doc == "history.csv"
    assert result["question_results"][0].references[0].used_for_answer is True
    assert result["question_results"][0].grounding_status == "grounded"
    assert result["question_results"][0].confidence_level == "high"
    assert result["question_results"][0].risk.level == "medium"
    assert result["question_results"][1].generated_answer is None
    assert result["question_results"][1].status == "unanswered"
    assert result["question_results"][1].grounding_status == "no_reference"
    assert (
        result["question_results"][1].confidence_reason
        == "Insufficient supporting evidence to answer safely."
    )
    assert result["question_results"][1].references == []
    assert result["summary"].total_questions_processed == 2
    assert result["summary"].completed_questions == 1
    assert result["summary"].unanswered_questions == 1


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
                    references=[
                        HistoricalReference(
                            record_id="qa-1",
                            question="Historical TLS question",
                            answer="Historical TLS answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.95,
                        )
                    ],
                ),
                "q-003": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-2",
                    question="Historical SSO question",
                    answer="Historical SSO answer",
                    domain="Architecture",
                    source_doc="history.csv",
                    alignment_score=0.94,
                    references=[
                        HistoricalReference(
                            record_id="qa-2",
                            question="Historical SSO question",
                            answer="Historical SSO answer",
                            domain="Architecture",
                            source_doc="history.csv",
                            alignment_score=0.94,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-001": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-1"],
                    reason="Historical answer is sufficient.",
                ),
                "q-003": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-2"],
                    reason="Historical answer is sufficient.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
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
                    references=[
                        HistoricalReference(
                            record_id="qa-4",
                            question="Historical FedRAMP question",
                            answer="We do not hold FedRAMP authorisation.",
                            domain="Compliance",
                            source_doc="history.csv",
                            alignment_score=0.35,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-004": ReferenceAssessmentResult(
                    can_answer=False,
                    grounding_status="insufficient_reference",
                    usable_reference_ids=[],
                    reason="Candidate references are not sufficient.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
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

    assert result["question_results"][0].generated_answer is None
    assert result["question_results"][0].grounding_status == "insufficient_reference"
    assert (
        result["question_results"][0].references[0].matched_question
        == "Historical FedRAMP question"
    )
    assert result["question_results"][0].references[0].used_for_answer is False
    assert result["question_results"][0].status == "unanswered"
    assert (
        result["question_results"][0].confidence_reason
        == "Candidate references are not sufficient."
    )
    assert result["question_results"][0].risk.level == "low"
    assert result["summary"].flagged_high_risk_or_inconsistent_responses == 0
    assert result["summary"].overall_completion_status == "unanswered"


async def test_tender_response_graph_marks_batch_unanswered_when_no_answers_are_generated() -> None:
    workflow = create_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-010": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.33,
                    references=[],
                )
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-010": ReferenceAssessmentResult(
                    can_answer=False,
                    grounding_status="no_reference",
                    usable_reference_ids=[],
                    reason="No usable historical references.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-3",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-010",
                    original_question="Are you FedRAMP High authorized?",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
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

    assert result["question_results"][0].status == "unanswered"
    assert result["summary"].overall_completion_status == "unanswered"
    assert result["summary"].completed_questions == 0
    assert result["summary"].unanswered_questions == 1
