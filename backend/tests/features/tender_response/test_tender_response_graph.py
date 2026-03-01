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
        attempt_number: int = 1,
        validation_error: str | None = None,
        last_invalid_answer: str | None = None,
        last_invalid_confidence_level: str | None = None,
        last_invalid_confidence_reason: str | None = None,
        assessment_reason: str | None = None,
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


class ConfigurableAnswerGenerationService:
    def __init__(self, results: dict[str, GroundedAnswerResult]) -> None:
        self.results = results
        self.answer_calls: list[str] = []

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
        self.answer_calls.append(question.question_id)
        return self.results[question.question_id]


class SequentialAnswerGenerationService:
    def __init__(self, results: dict[str, list[GroundedAnswerResult]]) -> None:
        self.results = results
        self.answer_calls: list[str] = []
        self._call_counts: dict[str, int] = {}

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
        self.answer_calls.append(question.question_id)
        attempt_index = self._call_counts.get(question.question_id, 0)
        self._call_counts[question.question_id] = attempt_index + 1
        return self.results[question.question_id][attempt_index]


class FakeReferenceAssessmentService:
    def __init__(self, results: dict[str, ReferenceAssessmentResult]) -> None:
        self.results = results

    async def assess(self, *, question: TenderQuestion, references):
        return self.results[question.question_id]


async def test_tender_response_graph_processes_any_number_of_questions() -> None:
    answer_service = FakeAnswerGenerationService()
    workflow = create_parallel_tender_response_graph(
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
    assert result["question_results"][1].confidence_level is None
    assert result["question_results"][1].confidence_reason is None
    assert result["question_results"][1].references == []
    assert result["summary"].total_questions_processed == 2
    assert result["summary"].completed_questions == 1
    assert result["summary"].unanswered_questions == 1


async def test_tender_response_graph_keeps_processing_when_one_question_fails() -> None:
    workflow = create_parallel_tender_response_graph(
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
        },
        config={"configurable": {"thread_id": "session-2"}},
    )

    statuses = {item.question_id: item.status for item in result["question_results"]}
    assert statuses["q-001"] == "completed"
    assert statuses["q-003"] == "failed"
    assert result["summary"].overall_completion_status == "partial_failure"


async def test_tender_response_graph_marks_flagged_responses_in_summary() -> None:
    workflow = create_parallel_tender_response_graph(
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
    assert result["question_results"][0].confidence_level is None
    assert result["question_results"][0].confidence_reason is None
    assert result["question_results"][0].risk.level == "low"
    assert result["summary"].flagged_high_risk_or_inconsistent_responses == 0
    assert result["summary"].overall_completion_status == "unanswered"


async def test_tender_response_graph_marks_batch_unanswered_when_no_answers_are_generated() -> None:
    workflow = create_parallel_tender_response_graph(
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
        },
        config={"configurable": {"thread_id": "session-3"}},
    )

    assert result["question_results"][0].status == "unanswered"
    assert result["summary"].overall_completion_status == "unanswered"
    assert result["summary"].completed_questions == 0
    assert result["summary"].unanswered_questions == 1


async def test_tender_response_graph_leaves_unanswered_confidence_fields_null() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-005": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.22,
                    references=[],
                ),
            }
        ),
        answer_generation_service=FakeAnswerGenerationService(),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-005": ReferenceAssessmentResult(
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
            "session_id": "session-5",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-005",
                    original_question="Provide your FedRAMP package identifier.",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-5"}},
    )

    unanswered = result["question_results"][0]

    assert unanswered.status == "unanswered"
    assert unanswered.generated_answer is None
    assert unanswered.confidence_level is None
    assert unanswered.confidence_reason is None


async def test_tender_response_graph_preserves_partial_answers_when_scope_is_missing() -> None:
    answer_service = ConfigurableAnswerGenerationService(
        {
            "q-006": GroundedAnswerResult(
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
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-006": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-6",
                    question="Describe your hosting controls.",
                    answer="Regional hosting controls are available by deployment.",
                    domain="Compliance",
                    source_doc="compliance-history.csv",
                    alignment_score=0.66,
                    references=[
                        HistoricalReference(
                            record_id="qa-6",
                            question="Describe your hosting controls.",
                            answer="Regional hosting controls are available by deployment.",
                            domain="Compliance",
                            source_doc="compliance-history.csv",
                            alignment_score=0.66,
                        ),
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-006": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-6"],
                    reason="Regional hosting references do not cover sovereign guarantees.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-6",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-006",
                    original_question="Describe your sovereign hosting guarantees.",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-6"}},
    )

    partial = result["question_results"][0]

    assert answer_service.answer_calls == ["q-006"]
    assert partial.status == "completed"
    assert partial.grounding_status == "partial_reference"
    assert partial.generated_answer is not None
    assert "(" in partial.generated_answer and ")" in partial.generated_answer
    assert partial.confidence_level == "medium"
    assert "Confidence is reduced because" in (partial.confidence_reason or "")
    assert "do not evidence jurisdiction-specific sovereign hosting guarantees" in (
        partial.confidence_reason or ""
    )


async def test_tender_response_graph_keeps_supported_high_risk_answers_completed_with_flags() -> None:
    answer_service = ConfigurableAnswerGenerationService(
        {
            "q-007": GroundedAnswerResult(
                generated_answer="Yes, we are FedRAMP authorized.",
                confidence_level="low",
                confidence_reason=(
                    "Confidence is reduced because the references do not evidence a "
                    "FedRAMP authorization."
                ),
                risk_level="high",
                risk_reason="This answer introduces a certification claim not supported by history.",
                inconsistent_response=False,
            ),
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-007": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-7",
                    question="Are you FedRAMP authorized?",
                    answer="We do not hold FedRAMP authorisation.",
                    domain="Compliance",
                    source_doc="compliance-history.csv",
                    alignment_score=0.77,
                    references=[
                        HistoricalReference(
                            record_id="qa-7",
                            question="Are you FedRAMP authorized?",
                            answer="We do not hold FedRAMP authorisation.",
                            domain="Compliance",
                            source_doc="compliance-history.csv",
                            alignment_score=0.77,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-007": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-7"],
                    reason="The historical answer directly addresses the certification question.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-7",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-007",
                    original_question="Are you FedRAMP authorized?",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-7"}},
    )

    flagged = result["question_results"][0]

    assert flagged.status == "completed"
    assert flagged.generated_answer == "Yes, we are FedRAMP authorized."
    assert flagged.flags.high_risk is True
    assert flagged.risk.level == "high"
    assert result["summary"].flagged_high_risk_or_inconsistent_responses == 1


async def test_tender_response_graph_fails_partial_answers_that_do_not_disclose_missing_scope() -> None:
    answer_service = ConfigurableAnswerGenerationService(
        {
            "q-008": GroundedAnswerResult(
                generated_answer="We support regional hosting controls.",
                confidence_level="high",
                confidence_reason="The answer is supported.",
                risk_level="low",
                risk_reason="Low delivery risk.",
                inconsistent_response=False,
            ),
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-008": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-8",
                    question="Describe your hosting controls.",
                    answer="Regional hosting controls are available by deployment.",
                    domain="Compliance",
                    source_doc="compliance-history.csv",
                    alignment_score=0.67,
                    references=[
                        HistoricalReference(
                            record_id="qa-8",
                            question="Describe your hosting controls.",
                            answer="Regional hosting controls are available by deployment.",
                            domain="Compliance",
                            source_doc="compliance-history.csv",
                            alignment_score=0.67,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-008": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-8"],
                    reason="The references support hosting controls but not sovereign guarantees.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-8",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-008",
                    original_question="Describe your sovereign hosting guarantees.",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-8"}},
    )

    failed = result["question_results"][0]

    assert failed.status == "failed"
    assert failed.error_message is not None
    assert "partial answer" in failed.error_message.lower()


async def test_tender_response_graph_retries_invalid_partial_reference_until_second_attempt_is_valid() -> None:
    answer_service = SequentialAnswerGenerationService(
        {
            "q-011": [
                GroundedAnswerResult(
                    generated_answer="We support regional hosting controls.",
                    confidence_level="high",
                    confidence_reason="The answer is supported.",
                    risk_level="medium",
                    risk_reason="Human review is still required.",
                    inconsistent_response=False,
                ),
                GroundedAnswerResult(
                    generated_answer=(
                        "We support regional hosting controls (jurisdiction-specific "
                        "sovereign hosting guarantees are not evidenced in the "
                        "retrieved references)."
                    ),
                    confidence_level="medium",
                    confidence_reason=(
                        "Confidence is reduced because the retrieved references support "
                        "regional hosting controls but do not evidence "
                        "jurisdiction-specific sovereign hosting guarantees."
                    ),
                    risk_level="medium",
                    risk_reason="Human review is still required.",
                    inconsistent_response=False,
                ),
            ]
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-011": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-11",
                    question="Describe your hosting controls.",
                    answer="Regional hosting controls are available by deployment.",
                    domain="Compliance",
                    source_doc="compliance-history.csv",
                    alignment_score=0.71,
                    references=[
                        HistoricalReference(
                            record_id="qa-11",
                            question="Describe your hosting controls.",
                            answer="Regional hosting controls are available by deployment.",
                            domain="Compliance",
                            source_doc="compliance-history.csv",
                            alignment_score=0.71,
                        )
                    ],
                )
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-011": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-11"],
                    reason="The references support hosting controls but not sovereign guarantees.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-11",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-011",
                    original_question="Describe your sovereign hosting guarantees.",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-11"}},
    )

    partial = result["question_results"][0]

    assert partial.status == "completed"
    assert partial.grounding_status == "partial_reference"
    assert partial.generated_answer is not None
    assert "(" in partial.generated_answer and ")" in partial.generated_answer
    assert partial.confidence_level == "medium"
    assert answer_service.answer_calls == ["q-011", "q-011"]


async def test_tender_response_graph_fails_partial_reference_after_three_invalid_attempts() -> None:
    answer_service = SequentialAnswerGenerationService(
        {
            "q-012": [
                GroundedAnswerResult(
                    generated_answer="We support regional hosting controls.",
                    confidence_level="high",
                    confidence_reason="The answer is supported.",
                    risk_level="medium",
                    risk_reason="Human review is still required.",
                    inconsistent_response=False,
                ),
                GroundedAnswerResult(
                    generated_answer="We support regional hosting controls.",
                    confidence_level="high",
                    confidence_reason="The answer is supported.",
                    risk_level="medium",
                    risk_reason="Human review is still required.",
                    inconsistent_response=False,
                ),
                GroundedAnswerResult(
                    generated_answer="We support regional hosting controls.",
                    confidence_level="high",
                    confidence_reason="The answer is supported.",
                    risk_level="medium",
                    risk_reason="Human review is still required.",
                    inconsistent_response=False,
                ),
            ]
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-012": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-12",
                    question="Describe your hosting controls.",
                    answer="Regional hosting controls are available by deployment.",
                    domain="Compliance",
                    source_doc="compliance-history.csv",
                    alignment_score=0.69,
                    references=[
                        HistoricalReference(
                            record_id="qa-12",
                            question="Describe your hosting controls.",
                            answer="Regional hosting controls are available by deployment.",
                            domain="Compliance",
                            source_doc="compliance-history.csv",
                            alignment_score=0.69,
                        )
                    ],
                )
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-012": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-12"],
                    reason="The references support hosting controls but not sovereign guarantees.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-12",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-012",
                    original_question="Describe your sovereign hosting guarantees.",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-12"}},
    )

    failed = result["question_results"][0]

    assert failed.status == "failed"
    assert failed.grounding_status == "failed"
    assert failed.error_message is not None
    assert "partial answer" in failed.error_message.lower()
    assert answer_service.answer_calls == ["q-012", "q-012", "q-012"]
