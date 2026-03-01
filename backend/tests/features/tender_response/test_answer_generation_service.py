from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)


class FakeStructuredRunnable:
    def __init__(self, schema, responses: dict | list[dict], all_calls: list[list]) -> None:
        self._schema = schema
        self._responses = responses if isinstance(responses, list) else [responses]
        self._all_calls = all_calls

    async def ainvoke(self, messages):
        self._all_calls.append(messages)
        payload = self._responses[0] if len(self._responses) == 1 else self._responses.pop(0)
        return self._schema(**payload)


class FakeChatModel:
    def __init__(self, responses: dict | list[dict]) -> None:
        self.responses = responses
        self.schema = None
        self.method = None
        self.strict = None
        self.calls: list[list] = []

    def with_structured_output(self, schema, *, method, strict):
        self.schema = schema
        self.method = method
        self.strict = strict
        return FakeStructuredRunnable(schema, self.responses, self.calls)


class FakeChatModelFactory:
    def __init__(self) -> None:
        self.model: str | None = None
        self.temperature: float | None = None

    def __call__(self, *, model: str, temperature: float):
        self.model = model
        self.temperature = temperature
        return FakeChatModel(
            {
                "generated_answer": "unused",
                "confidence_level": "high",
                "confidence_reason": "unused",
                "risk_level": "low",
                "risk_reason": "unused",
                "inconsistent_response": False,
            }
        )


def test_answer_generation_service_uses_dedicated_tender_model_configuration(
    monkeypatch,
) -> None:
    factory = FakeChatModelFactory()
    monkeypatch.setattr(
        "app.features.tender_response.infrastructure.services.answer_generation_service."
        "ChatOpenAI",
        factory,
    )
    monkeypatch.setattr(
        "app.features.tender_response.infrastructure.services.answer_generation_service."
        "settings.openai_tender_response_model",
        "gpt-test-tender",
    )

    AnswerGenerationService()

    assert factory.model == "gpt-test-tender"
    assert factory.temperature == 0


async def test_generate_grounded_response_uses_historical_context_and_returns_review() -> None:
    model = FakeChatModel(
        {
            "generated_answer": "Aligned answer",
            "confidence_level": "high",
            "confidence_reason": "Historical evidence directly supports the answer.",
            "risk_level": "medium",
            "risk_reason": "Security responses still need review.",
            "inconsistent_response": False,
        }
    )
    service = AnswerGenerationService(model=model)

    result = await service.generate_grounded_response(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        usable_references=[
            HistoricalReference(
                record_id="qa-1",
                question="Do you support TLS 1.2 or higher?",
                answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
                domain="Security",
                source_doc="history.csv",
                alignment_score=0.93,
            )
        ],
    )

    assert result.generated_answer == "Aligned answer"
    assert result.confidence_level == "high"
    assert result.risk_level == "medium"
    assert model.method == "json_schema"
    assert model.strict is True
    rendered_messages = model.calls[0]
    assert "Reference 1 answer" in rendered_messages[1].content
    assert "confidence_level=high" in rendered_messages[1].content.lower()
    assert "do not fabricate" in rendered_messages[0].content.lower()


async def test_generate_grounded_response_rewrites_invalid_structured_answer_output() -> None:
    model = FakeChatModel(
        [
            {
                "generated_answer": "{'RPO': '15 minutes', 'RTO': '4 hours'}",
                "confidence_level": "high",
                "confidence_reason": "Historical evidence directly supports the answer.",
                "risk_level": "medium",
                "risk_reason": "Operational targets should be reviewed.",
                "inconsistent_response": False,
            },
            {
                "generated_answer": (
                    "The documented production disaster recovery targets are "
                    "an RPO of 15 minutes and an RTO of 4 hours."
                ),
                "confidence_level": "high",
                "confidence_reason": "Historical evidence directly supports the answer.",
                "risk_level": "medium",
                "risk_reason": "Operational targets should be reviewed.",
                "inconsistent_response": False,
            },
        ]
    )
    service = AnswerGenerationService(model=model)

    result = await service.generate_grounded_response(
        question=TenderQuestion(
            question_id="q-002",
            original_question=(
                "Please confirm your production disaster recovery targets, "
                "including RPO and RTO."
            ),
            declared_domain="Infrastructure",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        usable_references=[
            HistoricalReference(
                record_id="qa-2",
                question="What are your production disaster recovery targets?",
                answer=(
                    "The documented production disaster recovery targets are an "
                    "RPO of 15 minutes and an RTO of 4 hours."
                ),
                domain="Infrastructure",
                source_doc="history.csv",
                alignment_score=0.91,
            )
        ],
    )

    assert result.generated_answer.startswith("The documented production disaster recovery targets")
    assert len(model.calls) == 2
    assert (
        "rewrite" in model.calls[1][0].content.lower()
        or "rewrite" in model.calls[1][1].content.lower()
    )
