from app.features.tender_response.domain.models import HistoricalAlignmentResult, TenderQuestion
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)


class FakeCompletionClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def create_completion(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


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


async def test_generate_answer_with_alignment_uses_historical_context() -> None:
    client = FakeCompletionClient("Aligned answer")
    service = AnswerGenerationService(completion_client=client)

    answer = await service.generate_with_alignment(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        alignment=HistoricalAlignmentResult(
            matched=True,
            record_id="qa-1",
            question="Do you support TLS 1.2 or higher?",
            answer="Yes. Production traffic is restricted to TLS 1.2 or higher.",
            domain="Security",
            source_doc="history.csv",
            alignment_score=0.93,
        ),
    )

    assert answer == "Aligned answer"
    assert "Historical answer" in client.calls[0][1]


async def test_generate_answer_without_alignment_uses_conservative_prompting() -> None:
    client = FakeCompletionClient("Conservative answer")
    service = AnswerGenerationService(completion_client=client)

    answer = await service.generate_without_alignment(
        TenderQuestion(
            question_id="q-002",
            original_question="Are you FedRAMP authorised?",
            declared_domain="Compliance",
            source_file_name="tender.csv",
            source_row_index=1,
        )
    )

    assert answer == "Conservative answer"
    assert "do not fabricate" in client.calls[0][0].lower()
