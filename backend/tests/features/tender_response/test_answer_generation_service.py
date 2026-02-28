from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)


class FakeCompletionClient:
    def __init__(self, response: str | list[str]) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[tuple[str, str]] = []

    async def create_json_completion(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


class FakeCompletionClientFactory:
    def __init__(self) -> None:
        self.model: str | None = None

    def __call__(self, *, model: str):
        self.model = model
        return FakeCompletionClient("unused")


def test_answer_generation_service_uses_dedicated_tender_model_configuration(
    monkeypatch,
) -> None:
    factory = FakeCompletionClientFactory()
    monkeypatch.setattr(
        "app.features.tender_response.infrastructure.services.answer_generation_service."
        "OpenAIChatCompletionsClient",
        factory,
    )
    monkeypatch.setattr(
        "app.features.tender_response.infrastructure.services.answer_generation_service."
        "settings.openai_tender_response_model",
        "gpt-test-tender",
    )

    AnswerGenerationService()

    assert factory.model == "gpt-test-tender"


async def test_generate_grounded_response_uses_historical_context_and_returns_review() -> None:
    client = FakeCompletionClient(
        '{"generated_answer":"Aligned answer","confidence_level":"high",'
        '"confidence_reason":"Historical evidence directly supports the answer.",'
        '"risk_level":"medium","risk_reason":"Security responses still need review.",'
        '"inconsistent_response":false}'
    )
    service = AnswerGenerationService(completion_client=client)

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
    assert "Reference 1 answer" in client.calls[0][1]
    assert "strict json" in client.calls[0][0].lower()
    assert "confidence_level=high" in client.calls[0][1].lower()
    assert "confidence_level=medium" in client.calls[0][1].lower()
    assert "confidence_level=low" in client.calls[0][1].lower()


async def test_generate_grounded_response_rewrites_invalid_structured_answer_output() -> None:
    client = FakeCompletionClient(
        [
            '{"generated_answer":"{\'RPO\': \'15 minutes\', \'RTO\': \'4 hours\'}",'
            '"confidence_level":"high",'
            '"confidence_reason":"Historical evidence directly supports the answer.",'
            '"risk_level":"medium","risk_reason":"Operational targets should be reviewed.",'
            '"inconsistent_response":false}',
            '{"generated_answer":"The documented production disaster recovery targets are '
            'an RPO of 15 minutes and an RTO of 4 hours.",'
            '"confidence_level":"high",'
            '"confidence_reason":"Historical evidence directly supports the answer.",'
            '"risk_level":"medium","risk_reason":"Operational targets should be reviewed.",'
            '"inconsistent_response":false}',
        ]
    )
    service = AnswerGenerationService(completion_client=client)

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
    assert len(client.calls) == 2
    assert "rewrite" in client.calls[1][0].lower() or "rewrite" in client.calls[1][1].lower()
