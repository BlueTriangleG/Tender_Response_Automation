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
    model = FakeChatModel({"can_answer": True, "usable_reference_ids": [], "reason": "unused"})
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
        {"can_answer": True, "usable_reference_ids": ["qa-1"], "reason": "Enough evidence."}
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
    assert "Only mark can_answer=true" in model.runnable.calls[0][1].content


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


def test_reference_assessment_payload_marks_all_properties_as_required_for_strict_function_calling() -> None:
    schema = _ReferenceAssessmentPayload.model_json_schema()

    assert sorted(schema["required"]) == [
        "can_answer",
        "reason",
        "usable_reference_ids",
    ]
