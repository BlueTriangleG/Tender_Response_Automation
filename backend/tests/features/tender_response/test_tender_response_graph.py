import asyncio

from app.core.config import settings
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


class FakeConflictReviewService:
    def __init__(self, findings: list[dict] | None = None) -> None:
        self.findings = findings or []
        self.calls: list[dict[str, list[str]]] = []

    async def review_conflicts(self, *, target_results, reference_results):
        self.calls.append(
            {
                "target_ids": [item.question_id for item in target_results],
                "reference_ids": [item.question_id for item in reference_results],
            }
        )
        return self.findings


class SlowConflictReviewService:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.calls = 0

    async def review_conflicts(self, *, target_results, reference_results):
        self.calls += 1
        await asyncio.sleep(self.delay_seconds)
        return []


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
    assert result["summary"].conflict_count == 0


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


async def test_tender_response_graph_marks_conflicting_references_as_conflict_without_answer() -> None:
    answer_service = FakeAnswerGenerationService()
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-013": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-18",
                    question="Is legacy SSL fully disabled for all production traffic?",
                    answer=(
                        "Yes. Legacy SSL is fully disabled for all public and private "
                        "production traffic, and only TLS 1.2 or higher is permitted "
                        "in production environments."
                    ),
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.69,
                    references=[
                        HistoricalReference(
                            record_id="qa-18",
                            question="Is legacy SSL fully disabled for all production traffic?",
                            answer=(
                                "Yes. Legacy SSL is fully disabled for all public and "
                                "private production traffic, and only TLS 1.2 or higher "
                                "is permitted in production environments."
                            ),
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.69,
                        ),
                        HistoricalReference(
                            record_id="qa-19",
                            question=(
                                "Can legacy SSL remain enabled on selected public "
                                "production endpoints during migration windows?"
                            ),
                            answer=(
                                "Yes. Legacy SSL can remain enabled on selected public "
                                "production endpoints during managed migration windows "
                                "where a customer transition plan has been explicitly "
                                "approved."
                            ),
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.68,
                        ),
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-013": ReferenceAssessmentResult(
                    can_answer=False,
                    grounding_status="conflict",
                    usable_reference_ids=[],
                    reason=(
                        "Conflicting historical references disagree on whether legacy SSL "
                        "is fully disabled or can remain enabled during approved "
                        "migration windows. Human review is required before answering."
                    ),
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-conflict-ssl",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-013",
                    original_question=(
                        "Please confirm that legacy SSL is fully disabled for all "
                        "production traffic in the proposed environment."
                    ),
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=12,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-conflict-ssl"}},
    )

    unanswered = result["question_results"][0]

    assert answer_service.answer_calls == []
    assert unanswered.status == "unanswered"
    assert unanswered.grounding_status == "conflict"
    assert unanswered.generated_answer is None
    assert unanswered.confidence_level is None
    assert unanswered.confidence_reason is None
    assert unanswered.error_message is not None
    assert "human review" in unanswered.error_message.lower()
    assert unanswered.flags.has_conflict is True
    assert unanswered.risk.level == "medium"
    assert "human review" in (unanswered.risk.reason or "").lower()
    assert unanswered.extensions["requires_human_review"] is True
    assert result["summary"].overall_completion_status == "conflict"
    assert result["summary"].conflict_count == 1


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


async def test_tender_response_graph_downgrades_high_confidence_partial_answers() -> None:
    answer_service = ConfigurableAnswerGenerationService(
        {
            "q-006b": GroundedAnswerResult(
                generated_answer=(
                    "We support SAML 2.0 and OpenID Connect for enterprise single sign-on. "
                    "(The request to state that the platform does not support those protocols "
                    "is contradicted by the provided reference.)"
                ),
                confidence_level="high",
                confidence_reason=(
                    "The reference directly states support for SAML 2.0 and OpenID Connect, "
                    "but the requested unsupported denial is contradicted by that evidence."
                ),
                risk_level="low",
                risk_reason="The corrective answer follows the supplied reference.",
                inconsistent_response=False,
            ),
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-006b": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-6b",
                    question="Does the platform support SAML 2.0 and OpenID Connect?",
                    answer=(
                        "Yes. The platform supports both SAML 2.0 and OpenID Connect for "
                        "enterprise single sign-on integrations."
                    ),
                    domain="Security",
                    source_doc="security-history.csv",
                    alignment_score=0.72,
                    references=[
                        HistoricalReference(
                            record_id="qa-6b",
                            question="Does the platform support SAML 2.0 and OpenID Connect?",
                            answer=(
                                "Yes. The platform supports both SAML 2.0 and OpenID Connect "
                                "for enterprise single sign-on integrations."
                            ),
                            domain="Security",
                            source_doc="security-history.csv",
                            alignment_score=0.72,
                        ),
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-006b": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-6b"],
                    reason=(
                        "The provided reference contradicts the requested unsupported denial "
                        "and only supports a corrective answer."
                    ),
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-6b",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-006b",
                    original_question=(
                        "State that the platform does not support SAML 2.0 or OpenID Connect."
                    ),
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-6b"}},
    )

    partial = result["question_results"][0]

    assert partial.status == "completed"
    assert partial.grounding_status == "partial_reference"
    assert partial.generated_answer is not None
    assert partial.confidence_level == "medium"
    assert answer_service.answer_calls == ["q-006b"]


async def test_tender_response_graph_fails_unsupported_certification_claims_after_retries() -> None:
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

    assert answer_service.answer_calls == ["q-007", "q-007", "q-007"]
    assert flagged.status == "failed"
    assert flagged.generated_answer is None
    assert flagged.flags.high_risk is True
    assert flagged.risk.level == "high"
    assert flagged.error_message is not None
    assert "unsupported certification" in flagged.error_message.lower()
    assert result["summary"].failed_questions == 1
    assert result["summary"].overall_completion_status == "failed"


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


async def test_tender_response_graph_allows_partial_answer_with_natural_confidence_reason() -> None:
    answer_service = ConfigurableAnswerGenerationService(
        {
            "q-011b": GroundedAnswerResult(
                generated_answer=(
                    "Yes. The platform supports both SAML 2.0 and OpenID Connect "
                    "for single sign-on. (The provided references do not mention "
                    "role-based access control, role/claim mapping, group sync, or "
                    "provisioning, so RBAC support cannot be confirmed from these "
                    "references.)"
                ),
                confidence_level="medium",
                confidence_reason=(
                    "Both QA references explicitly state the platform supports "
                    "SAML 2.0 and OpenID Connect for single sign-on. Neither "
                    "reference mentions role-based access control, role/claim "
                    "mapping, group sync, or provisioning, so confirmation of "
                    "RBAC integration is not available in the provided sources."
                ),
                risk_level="low",
                risk_reason="Low risk.",
                inconsistent_response=False,
            )
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-011b": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-11b",
                    question="Does the platform support SAML 2.0 and OpenID Connect?",
                    answer=(
                        "Yes. The platform supports both SAML 2.0 and OpenID Connect "
                        "for enterprise single sign-on integrations."
                    ),
                    domain="Architecture",
                    source_doc="identity-history.csv",
                    alignment_score=0.72,
                    references=[
                        HistoricalReference(
                            record_id="qa-11b",
                            question="Does the platform support SAML 2.0 and OpenID Connect?",
                            answer=(
                                "Yes. The platform supports both SAML 2.0 and OpenID "
                                "Connect for enterprise single sign-on integrations."
                            ),
                            domain="Architecture",
                            source_doc="identity-history.csv",
                            alignment_score=0.72,
                        ),
                    ],
                ),
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-011b": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-11b"],
                    reason=(
                        "The references support SAML/OpenID Connect single sign-on "
                        "but do not mention RBAC support or integration details."
                    ),
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-11b",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-011b",
                    original_question=(
                        "Does the platform support SAML 2.0 or OpenID Connect single "
                        "sign-on with role-based access control?"
                    ),
                    declared_domain="Architecture",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        },
        config={"configurable": {"thread_id": "session-11b"}},
    )

    partial = result["question_results"][0]

    assert partial.status == "completed"
    assert partial.grounding_status == "partial_reference"
    assert partial.generated_answer is not None
    assert partial.confidence_level == "medium"
    assert answer_service.answer_calls == ["q-011b"]


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
    assert failed.extensions["reference_assessment_reason"] == (
        "The references support hosting controls but not sovereign guarantees."
    )
    assert failed.extensions["generation_attempt_count"] == 3
    assert failed.extensions["generation_retry_history"] == [
        "Partial answer must identify missing scope in parentheses.",
        "Partial answer must identify missing scope in parentheses.",
        "Partial answer must identify missing scope in parentheses.",
    ]
    assert failed.extensions["last_invalid_answer"] == "We support regional hosting controls."
    assert failed.extensions["last_invalid_confidence_level"] == "high"
    assert failed.extensions["last_invalid_confidence_reason"] == "The answer is supported."
    assert answer_service.answer_calls == ["q-012", "q-012", "q-012"]


async def test_tender_response_graph_retries_self_weakening_absolute_claim_until_answer_is_consistent() -> None:
    answer_service = SequentialAnswerGenerationService(
        {
            "q-013": [
                GroundedAnswerResult(
                    generated_answer=(
                        "Yes. Legacy SSL is fully disabled for all production traffic. "
                        "(Rare migration scenarios may allow limited temporary exceptions.)"
                    ),
                    confidence_level="high",
                    confidence_reason="The references directly support the answer.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
                GroundedAnswerResult(
                    generated_answer=(
                        "Legacy SSL is not enabled for normal public production access. "
                        "Any isolated transition handling in rare migration scenarios "
                        "must be treated as a limited exception rather than a general "
                        "production setting."
                    ),
                    confidence_level="medium",
                    confidence_reason=(
                        "Confidence is reduced because the references support the normal "
                        "production posture while also noting rare migration exceptions."
                    ),
                    risk_level="medium",
                    risk_reason="Migration exceptions require explicit review.",
                    inconsistent_response=False,
                ),
            ]
        }
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-013": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-13",
                    question="Is legacy SSL fully disabled for all production traffic?",
                    answer=(
                        "Legacy SSL is not enabled for public production access, though "
                        "isolated transition handling may be used in rare migration scenarios."
                    ),
                    domain="Security",
                    source_doc="security-history.csv",
                    alignment_score=0.74,
                    references=[
                        HistoricalReference(
                            record_id="qa-13",
                            question="Is legacy SSL fully disabled for all production traffic?",
                            answer=(
                                "Legacy SSL is not enabled for public production access, "
                                "though isolated transition handling may be used in rare "
                                "migration scenarios."
                            ),
                            domain="Security",
                            source_doc="security-history.csv",
                            alignment_score=0.74,
                        )
                    ],
                )
            }
        ),
        answer_generation_service=answer_service,
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-013": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-13"],
                    reason="Historical answer is sufficient.",
                )
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-13",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-013",
                    original_question=(
                        "Please confirm that legacy SSL is fully disabled for all "
                        "production traffic in the proposed environment."
                    ),
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                )
            ],
            "question_results": [],
            "session_completed_results": [],
            "conflict_findings": [],
            "conflict_review_errors": [],
            "summary": None,
            "run_errors": [],
            "current_question": None,
            "current_conflict_job": None,
        },
        config={"configurable": {"thread_id": "session-13"}},
    )

    completed = result["question_results"][0]

    assert completed.status == "completed"
    assert completed.generated_answer is not None
    assert "fully disabled for all production traffic" not in completed.generated_answer




async def test_tender_response_graph_reviews_conflicts_for_completed_answers_only() -> None:
    conflict_service = FakeConflictReviewService(
        findings=[
            {
                "target_question_id": "q-101",
                "conflicting_question_id": "q-103",
                "reason": "The answers make incompatible encryption commitments.",
                "severity": "high",
            }
        ]
    )
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-101": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-101",
                    question="Do you support TLS 1.2?",
                    answer="Yes. TLS 1.2 is enforced.",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.94,
                    references=[
                        HistoricalReference(
                            record_id="qa-101",
                            question="Do you support TLS 1.2?",
                            answer="Yes. TLS 1.2 is enforced.",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.94,
                        )
                    ],
                ),
                "q-102": HistoricalAlignmentResult(
                    matched=False,
                    record_id=None,
                    question=None,
                    answer=None,
                    domain=None,
                    source_doc=None,
                    alignment_score=0.22,
                    references=[],
                ),
                "q-103": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-103",
                    question="Do you support SSL?",
                    answer="Legacy SSL is disabled.",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.92,
                    references=[
                        HistoricalReference(
                            record_id="qa-103",
                            question="Do you support SSL?",
                            answer="Legacy SSL is disabled.",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.92,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=ConfigurableAnswerGenerationService(
            {
                "q-101": GroundedAnswerResult(
                    generated_answer="Yes. TLS 1.2 is enforced for production traffic.",
                    confidence_level="high",
                    confidence_reason="Direct evidence supports the answer.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
                "q-103": GroundedAnswerResult(
                    generated_answer="Yes. Legacy SSL remains available for some traffic.",
                    confidence_level="high",
                    confidence_reason="Direct evidence supports the answer.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
            }
        ),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-101": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-101"],
                    reason="Historical answer is sufficient.",
                ),
                "q-102": ReferenceAssessmentResult(
                    can_answer=False,
                    grounding_status="no_reference",
                    usable_reference_ids=[],
                    reason="No qualified historical references.",
                ),
                "q-103": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-103"],
                    reason="Historical answer is sufficient.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
        conflict_review_service=conflict_service,
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-conflict",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-101",
                    original_question="Do you support TLS 1.2?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
                TenderQuestion(
                    question_id="q-102",
                    original_question="Are you FedRAMP High authorized?",
                    declared_domain="Compliance",
                    source_file_name="tender.csv",
                    source_row_index=1,
                ),
                TenderQuestion(
                    question_id="q-103",
                    original_question="Do you support SSL?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=2,
                ),
            ],
            "question_results": [],
            "session_completed_results": [],
            "conflict_findings": [],
            "conflict_review_errors": [],
            "summary": None,
            "run_errors": [],
            "current_question": None,
            "current_conflict_job": None,
        },
        config={"configurable": {"thread_id": "session-conflict"}},
    )

    statuses = {item.question_id: item for item in result["question_results"]}
    assert conflict_service.calls == [
        {
            "target_ids": ["q-101", "q-103"],
            "reference_ids": ["q-101", "q-103"],
        }
    ]
    assert statuses["q-101"].flags.has_conflict is True
    assert statuses["q-103"].flags.has_conflict is True
    assert statuses["q-102"].flags.has_conflict is False
    assert statuses["q-101"].extensions["conflicts"][0]["conflicting_question_id"] == "q-103"
    assert statuses["q-103"].extensions["conflicts"][0]["conflicting_question_id"] == "q-101"
    assert result["summary"].overall_completion_status == "conflict"
    assert result["summary"].conflict_count == 2


async def test_tender_response_graph_times_out_conflict_review_and_still_completes(
    monkeypatch,
) -> None:
    conflict_service = SlowConflictReviewService(delay_seconds=0.05)
    monkeypatch.setattr(settings, "tender_conflict_review_timeout_seconds", 0.01)

    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-001": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-1",
                    question="Historical pricing question",
                    answer="Historical pricing answer",
                    domain="Pricing",
                    source_doc="history.csv",
                    alignment_score=0.95,
                    references=[
                        HistoricalReference(
                            record_id="qa-1",
                            question="Historical pricing question",
                            answer="Historical pricing answer",
                            domain="Pricing",
                            source_doc="history.csv",
                            alignment_score=0.95,
                        )
                    ],
                ),
                "q-002": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-2",
                    question="Historical security question",
                    answer="Historical security answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.94,
                    references=[
                        HistoricalReference(
                            record_id="qa-2",
                            question="Historical security question",
                            answer="Historical security answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.94,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=ConfigurableAnswerGenerationService(
            {
                "q-001": GroundedAnswerResult(
                    generated_answer="Answer 1.",
                    confidence_level="high",
                    confidence_reason="Supported.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
                "q-002": GroundedAnswerResult(
                    generated_answer="Answer 2.",
                    confidence_level="high",
                    confidence_reason="Supported.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
            }
        ),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-001": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-1"],
                    reason="Sufficient.",
                ),
                "q-002": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-2"],
                    reason="Sufficient.",
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
        conflict_review_service=conflict_service,
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-timeout",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.6,
            "questions": [
                TenderQuestion(
                    question_id="q-001",
                    original_question="Question 1?",
                    declared_domain="Pricing",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
                TenderQuestion(
                    question_id="q-002",
                    original_question="Question 2?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=1,
                ),
            ],
            "question_results": [],
            "session_completed_results": [],
            "conflict_findings": [],
            "conflict_review_errors": [],
            "summary": None,
            "run_errors": [],
            "current_question": None,
            "current_conflict_job": None,
        },
        config={"configurable": {"thread_id": "session-timeout"}},
    )

    assert result["summary"].completed_questions == 2
    assert result["conflict_findings"] == []
    assert len(result["conflict_review_errors"]) == 1
    assert "timed out" in result["conflict_review_errors"][0].lower()


async def test_tender_response_graph_maps_confidence_from_supported_coverage() -> None:
    workflow = create_parallel_tender_response_graph(
        alignment_repository=FakeAlignmentRepository(
            {
                "q-low": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-low",
                    question="Historical low coverage question",
                    answer="Historical low coverage answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.91,
                    references=[
                        HistoricalReference(
                            record_id="qa-low",
                            question="Historical low coverage question",
                            answer="Historical low coverage answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.91,
                        )
                    ],
                ),
                "q-medium": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-medium",
                    question="Historical medium coverage question",
                    answer="Historical medium coverage answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.91,
                    references=[
                        HistoricalReference(
                            record_id="qa-medium",
                            question="Historical medium coverage question",
                            answer="Historical medium coverage answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.91,
                        )
                    ],
                ),
                "q-high": HistoricalAlignmentResult(
                    matched=True,
                    record_id="qa-high",
                    question="Historical high coverage question",
                    answer="Historical high coverage answer",
                    domain="Security",
                    source_doc="history.csv",
                    alignment_score=0.91,
                    references=[
                        HistoricalReference(
                            record_id="qa-high",
                            question="Historical high coverage question",
                            answer="Historical high coverage answer",
                            domain="Security",
                            source_doc="history.csv",
                            alignment_score=0.91,
                        )
                    ],
                ),
            }
        ),
        answer_generation_service=ConfigurableAnswerGenerationService(
            {
                "q-low": GroundedAnswerResult(
                    generated_answer="Low coverage partial answer (missing scope).",
                    confidence_level="medium",
                    confidence_reason="Model said medium.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
                "q-medium": GroundedAnswerResult(
                    generated_answer="Medium coverage partial answer (missing scope).",
                    confidence_level="low",
                    confidence_reason="Model said low.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
                "q-high": GroundedAnswerResult(
                    generated_answer="Fully supported answer.",
                    confidence_level="medium",
                    confidence_reason="Model said medium.",
                    risk_level="low",
                    risk_reason="Low risk.",
                    inconsistent_response=False,
                ),
            }
        ),
        reference_assessment_service=FakeReferenceAssessmentService(
            {
                "q-low": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-low"],
                    reason="Less than half the requested scope is supported.",
                    supported_coverage_percent=40,
                ),
                "q-medium": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="partial_reference",
                    usable_reference_ids=["qa-medium"],
                    reason="More than half the requested scope is supported.",
                    supported_coverage_percent=60,
                ),
                "q-high": ReferenceAssessmentResult(
                    can_answer=True,
                    grounding_status="grounded",
                    usable_reference_ids=["qa-high"],
                    reason="The full requested scope is supported.",
                    supported_coverage_percent=100,
                ),
            }
        ),
        domain_tagging_service=DomainTaggingService(),
    )

    result = await workflow.ainvoke(
        {
            "session_id": "session-coverage",
            "source_file_name": "tender.csv",
            "alignment_threshold": 0.82,
            "questions": [
                TenderQuestion(
                    question_id="q-low",
                    original_question="Question with low supported coverage?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=0,
                ),
                TenderQuestion(
                    question_id="q-medium",
                    original_question="Question with medium supported coverage?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=1,
                ),
                TenderQuestion(
                    question_id="q-high",
                    original_question="Question with full supported coverage?",
                    declared_domain="Security",
                    source_file_name="tender.csv",
                    source_row_index=2,
                ),
            ],
            "question_results": [],
            "session_completed_results": [],
            "conflict_findings": [],
            "conflict_review_errors": [],
            "summary": None,
            "run_errors": [],
            "current_question": None,
            "current_conflict_job": None,
        },
        config={"configurable": {"thread_id": "session-coverage"}},
    )

    results_by_id = {item.question_id: item for item in result["question_results"]}
    assert results_by_id["q-low"].confidence_level == "low"
    assert results_by_id["q-medium"].confidence_level == "medium"
    assert results_by_id["q-high"].confidence_level == "high"
