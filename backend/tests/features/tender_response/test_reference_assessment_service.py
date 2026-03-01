from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentService,
    _ReferenceAssessmentPayload,
)


class FakeStructuredRunnable:
    def __init__(self, schema, response: dict, should_raise: bool = False) -> None:
        self._schema = schema
        self._response = response
        self.should_raise = should_raise
        self.calls: list[list] = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if self.should_raise:
            raise RuntimeError("llm unavailable")
        return self._schema(**self._response)


class FakeChatModel:
    def __init__(self, response: dict, should_raise: bool = False) -> None:
        self.response = response
        self.should_raise = should_raise
        self.schema = None
        self.method = None
        self.strict = None
        self.runnable = None

    def with_structured_output(self, schema, *, method, strict):
        self.schema = schema
        self.method = method
        self.strict = strict
        self.runnable = FakeStructuredRunnable(
            schema,
            self.response,
            should_raise=self.should_raise,
        )
        return self.runnable


async def test_assess_returns_no_reference_without_llm_call() -> None:
    model = FakeChatModel(
        {"answerability": "grounded", "usable_reference_ids": [], "reason": "unused"}
    )
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        references=[],
    )

    assert result.can_answer is False
    assert result.grounding_status == "no_reference"
    assert model.runnable is None


async def test_assess_returns_grounded_when_llm_marks_references_sufficient() -> None:
    model = FakeChatModel(
        {
            "answerability": "grounded",
            "usable_reference_ids": ["qa-1"],
            "reason": "Enough evidence.",
        }
    )
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        references=[
            HistoricalReference(
                record_id="qa-1",
                question="Historical TLS question",
                answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                domain="Security",
                source_doc="history.csv",
                alignment_score=0.91,
            )
        ],
    )

    assert result.can_answer is True
    assert result.grounding_status == "grounded"
    assert result.usable_reference_ids == ["qa-1"]
    assert model.method == "function_calling"
    assert model.strict is True
    assert "Classify answerability as none, partial, or grounded." in model.runnable.calls[0][1].content


async def test_assess_returns_partial_reference_when_llm_marks_references_partial() -> None:
    model = FakeChatModel(
        {
            "answerability": "partial",
            "usable_reference_ids": ["qa-1"],
            "reason": "The references support deployment controls but not sovereign guarantees.",
        }
    )
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-002",
            original_question="Describe your sovereign hosting guarantees.",
            declared_domain="Compliance",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        references=[
            HistoricalReference(
                record_id="qa-1",
                question="Describe your hosting controls.",
                answer="Regional hosting controls are available by deployment.",
                domain="Compliance",
                source_doc="history.csv",
                alignment_score=0.88,
            )
        ],
    )

    assert result.can_answer is True
    assert result.grounding_status == "partial_reference"
    assert result.usable_reference_ids == ["qa-1"]
    assert "deployment controls" in result.reason


async def test_assess_renders_document_chunk_references_as_excerpts() -> None:
    model = FakeChatModel(
        {
            "answerability": "grounded",
            "usable_reference_ids": ["doc-1#0"],
            "reason": "The excerpt directly supports the answer.",
        }
    )
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-009",
            original_question="How often do you test disaster recovery?",
            declared_domain="Operations",
            source_file_name="tender.csv",
            source_row_index=8,
        ),
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
                alignment_score=0.86,
            )
        ],
    )

    assert result.can_answer is True
    rendered_prompt = model.runnable.calls[0][1].content
    assert '"reference_type": "document_chunk"' in rendered_prompt
    assert '"excerpt": "Quarterly recovery exercises are documented and reviewed."' in (
        rendered_prompt
    )
    assert '"matched_answer": ""' in rendered_prompt


async def test_assess_returns_insufficient_reference_when_llm_fails() -> None:
    model = FakeChatModel({}, should_raise=True)
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        references=[
            HistoricalReference(
                record_id="qa-1",
                question="Historical TLS question",
                answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                domain="Security",
                source_doc="history.csv",
                alignment_score=0.91,
            )
        ],
    )

    assert result.can_answer is False
    assert result.grounding_status == "insufficient_reference"
    assert result.usable_reference_ids == []


async def test_assess_returns_conflict_for_conflicting_ssl_history() -> None:
    model = FakeChatModel(
        {
            "answerability": "grounded",
            "usable_reference_ids": ["qa-1", "qa-2"],
            "reason": "unused",
        }
    )
    service = ReferenceAssessmentService(model=model)

    result = await service.assess(
        question=TenderQuestion(
            question_id="q-013",
            original_question=(
                "Please confirm that legacy SSL is fully disabled for all production "
                "traffic in the proposed environment."
            ),
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=12,
        ),
        references=[
            HistoricalReference(
                record_id="qa-1",
                question="Is legacy SSL fully disabled for all production traffic?",
                answer=(
                    "Yes. Legacy SSL is fully disabled for all public and private "
                    "production traffic, and only TLS 1.2 or higher is permitted in "
                    "production environments."
                ),
                domain="Security",
                source_doc="history.csv",
                alignment_score=0.91,
            ),
            HistoricalReference(
                record_id="qa-2",
                question=(
                    "Can legacy SSL remain enabled on selected public production "
                    "endpoints during migration windows?"
                ),
                answer=(
                    "Yes. Legacy SSL can remain enabled on selected public production "
                    "endpoints during managed migration windows where a customer "
                    "transition plan has been explicitly approved."
                ),
                domain="Security",
                source_doc="history.csv",
                alignment_score=0.89,
            ),
        ],
    )

    assert result.can_answer is False
    assert result.grounding_status == "conflict"
    assert result.usable_reference_ids == []
    assert "conflicting historical references" in result.reason.lower()
    assert "human review" in result.reason.lower()
    assert model.runnable is None


def test_reference_assessment_payload_marks_all_properties_as_required_for_strict_function_calling() -> None:
    schema = _ReferenceAssessmentPayload.model_json_schema()

    assert sorted(schema["required"]) == [
        "answerability",
        "reason",
        "usable_reference_ids",
    ]
