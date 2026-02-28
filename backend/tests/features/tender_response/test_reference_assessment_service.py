from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentService,
)


class FakeCompletionClient:
    def __init__(self, response: str, should_raise: bool = False) -> None:
        self.response = response
        self.should_raise = should_raise
        self.calls: list[tuple[str, str]] = []

    async def create_json_completion(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if self.should_raise:
            raise RuntimeError("llm unavailable")
        return self.response


async def test_assess_returns_no_reference_without_llm_call() -> None:
    client = FakeCompletionClient('{"can_answer": true}')
    service = ReferenceAssessmentService(completion_client=client)

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
    assert client.calls == []


async def test_assess_returns_grounded_when_llm_marks_references_sufficient() -> None:
    client = FakeCompletionClient(
        '{"can_answer": true, "usable_reference_ids": ["qa-1"], "reason": "Enough evidence."}'
    )
    service = ReferenceAssessmentService(completion_client=client)

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


async def test_assess_returns_insufficient_reference_when_llm_fails() -> None:
    client = FakeCompletionClient("", should_raise=True)
    service = ReferenceAssessmentService(completion_client=client)

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
