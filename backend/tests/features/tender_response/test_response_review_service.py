from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.features.tender_response.infrastructure.services.response_review_service import (
    ResponseReviewService,
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


async def test_review_response_returns_llm_confidence_and_risk() -> None:
    service = ResponseReviewService(
        completion_client=FakeCompletionClient(
            '{"confidence_level":"high","confidence_reason":"Direct evidence.",'
            '"risk_level":"high","risk_reason":"Certification claim requires scrutiny.",'
            '"inconsistent_response":false}'
        )
    )

    result = await service.review_response(
        question=TenderQuestion(
            question_id="q-001",
            original_question="Do you hold ISO 27001 certification?",
            declared_domain="Compliance",
            source_file_name="tender.csv",
            source_row_index=0,
        ),
        generated_answer="Yes, the platform is ISO 27001 certified.",
        grounding_status="grounded",
        references=[
            HistoricalReference(
                record_id="qa-1",
                question="Which certifications can you currently claim?",
                answer="The approved claims are ISO 27001 certification and SOC 2 Type II.",
                domain="Compliance",
                source_doc="history.csv",
                alignment_score=0.95,
            )
        ],
    )

    assert result.confidence_level == "high"
    assert result.risk_level == "high"
    assert result.inconsistent_response is False


async def test_review_response_caps_confidence_for_unanswered_states() -> None:
    client = FakeCompletionClient(
        '{"confidence_level":"high",'
        '"confidence_reason":"The references only partially cover the question.",'
        '"risk_level":"medium",'
        '"risk_reason":"Security posture responses still need review.",'
        '"inconsistent_response":false}'
    )
    service = ResponseReviewService(completion_client=client)

    result = await service.review_response(
        question=TenderQuestion(
            question_id="q-002",
            original_question="Do you support TLS 1.2 or higher?",
            declared_domain="Security",
            source_file_name="tender.csv",
            source_row_index=1,
        ),
        generated_answer=None,
        grounding_status="insufficient_reference",
        references=[],
    )

    assert result.confidence_level == "low"
    assert result.confidence_reason == "The references only partially cover the question."
    assert result.risk_level == "medium"
    assert len(client.calls) == 1


async def test_review_response_returns_safe_defaults_when_llm_fails() -> None:
    service = ResponseReviewService(completion_client=FakeCompletionClient("", should_raise=True))

    result = await service.review_response(
        question=TenderQuestion(
            question_id="q-003",
            original_question="Do you support SAML SSO?",
            declared_domain="Architecture",
            source_file_name="tender.csv",
            source_row_index=2,
        ),
        generated_answer="SAML 2.0 is supported.",
        grounding_status="grounded",
        references=[],
    )

    assert result.confidence_level == "low"
    assert result.risk_level == "medium"
    assert result.inconsistent_response is False
