from app.features.tender_response.infrastructure.services.conflict_review_service import (
    ConflictReviewService,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionRisk,
    TenderQuestionResponse,
)


class FakeStructuredRunnable:
    def __init__(self, schema, response: dict) -> None:
        self._schema = schema
        self._response = response

    async def ainvoke(self, messages):
        self.messages = messages
        return self._schema(**self._response)


class FakeChatModel:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.schema = None
        self.method = None
        self.strict = None

    def with_structured_output(self, schema, *, method, strict):
        self.schema = schema
        self.method = method
        self.strict = strict
        return FakeStructuredRunnable(schema, self.response)


def make_completed_result(question_id: str, question: str, answer: str) -> TenderQuestionResponse:
    return TenderQuestionResponse(
        question_id=question_id,
        original_question=question,
        generated_answer=answer,
        domain_tag="security",
        confidence_level="high",
        confidence_reason="Direct support.",
        historical_alignment_indicator=True,
        status="completed",
        grounding_status="grounded",
        flags=QuestionFlags(),
        risk=QuestionRisk(level="low", reason="Low risk."),
        metadata=QuestionMetadata(source_row_index=0, alignment_record_id="qa-1"),
        references=[],
        error_message=None,
        extensions={},
    )


async def test_conflict_review_service_filters_invalid_or_unknown_conflicts() -> None:
    service = ConflictReviewService(
        model=FakeChatModel(
            {
                "conflicts": [
                    {
                        "target_question_id": "q-1",
                        "conflicting_question_id": "q-2",
                        "reason": "These answers conflict.",
                        "severity": "high",
                    },
                    {
                        "target_question_id": "q-1",
                        "conflicting_question_id": "q-9",
                        "reason": "Unknown question id.",
                        "severity": "medium",
                    },
                    {
                        "target_question_id": "q-1",
                        "conflicting_question_id": "q-1",
                        "reason": "Self conflict.",
                        "severity": "low",
                    },
                    {
                        "target_question_id": "q-1",
                        "conflicting_question_id": "q-2",
                        "reason": "These answers conflict.",
                        "severity": "high",
                    },
                ]
            }
        )
    )

    findings = await service.review_conflicts(
        target_results=[
            make_completed_result(
                "q-1",
                "Does the platform support SAML 2.0?",
                "Yes. The platform supports SAML 2.0 and OpenID Connect.",
            )
        ],
        reference_results=[
            make_completed_result(
                "q-1",
                "Does the platform support SAML 2.0?",
                "Yes. The platform supports SAML 2.0 and OpenID Connect.",
            ),
            make_completed_result(
                "q-2",
                "State that the platform does not support SAML 2.0.",
                "The platform does not support SAML 2.0 or OpenID Connect.",
            ),
        ],
    )

    assert findings == [
        {
            "target_question_id": "q-1",
            "conflicting_question_id": "q-2",
            "reason": (
                "The answers make opposing statements about whether SAML or OpenID "
                "Connect is supported."
            ),
            "severity": "high",
        }
    ]
    assert service._model.method == "function_calling"
    assert service._model.strict is True


async def test_conflict_review_service_filters_llm_false_positive_for_unrelated_topics() -> None:
    service = ConflictReviewService(
        model=FakeChatModel(
            {
                "conflicts": [
                    {
                        "target_question_id": "q-2",
                        "conflicting_question_id": "q-11",
                        "reason": "These answers conflict.",
                        "severity": "high",
                    }
                ]
            }
        )
    )

    findings = await service.review_conflicts(
        target_results=[
            make_completed_result(
                "q-2",
                (
                    "Does the platform support SAML 2.0 or OpenID Connect single "
                    "sign-on with role-based access control?"
                ),
                (
                    "Yes. The platform supports both SAML 2.0 and OpenID Connect "
                    "single sign-on, and it provides role-based access control across "
                    "tenant, workspace, and feature levels."
                ),
            )
        ],
        reference_results=[
            make_completed_result(
                "q-2",
                (
                    "Does the platform support SAML 2.0 or OpenID Connect single "
                    "sign-on with role-based access control?"
                ),
                (
                    "Yes. The platform supports both SAML 2.0 and OpenID Connect "
                    "single sign-on, and it provides role-based access control across "
                    "tenant, workspace, and feature levels."
                ),
            ),
            make_completed_result(
                "q-11",
                (
                    "Can you commit to fixed pricing for five years including "
                    "unlimited AI token usage across all business units?"
                ),
                (
                    "We cannot commit to fixed pricing for five years that includes "
                    "unlimited AI token usage across all business units."
                ),
            ),
        ],
    )

    assert findings == []


async def test_conflict_review_service_filters_penetration_testing_vs_fedramp_false_positive() -> None:
    service = ConflictReviewService(
        model=FakeChatModel(
            {
                "conflicts": [
                    {
                        "target_question_id": "q-9",
                        "conflicting_question_id": "q-12",
                        "reason": "These answers conflict.",
                        "severity": "high",
                    }
                ]
            }
        )
    )

    findings = await service.review_conflicts(
        target_results=[
            make_completed_result(
                "q-9",
                (
                    "Do you perform independent penetration testing and can "
                    "evidence be shared during procurement under NDA?"
                ),
                (
                    "Yes. Independent penetration testing is performed at least "
                    "annually and after material architectural changes. The "
                    "provided references do not confirm whether evidence can be "
                    "shared under NDA."
                ),
            )
        ],
        reference_results=[
            make_completed_result(
                "q-9",
                (
                    "Do you perform independent penetration testing and can "
                    "evidence be shared during procurement under NDA?"
                ),
                (
                    "Yes. Independent penetration testing is performed at least "
                    "annually and after material architectural changes. The "
                    "provided references do not confirm whether evidence can be "
                    "shared under NDA."
                ),
            ),
            make_completed_result(
                "q-12",
                (
                    "Do you currently hold FedRAMP High authorization for the "
                    "platform environment proposed in this tender?"
                ),
                (
                    "I cannot assert that we currently hold FedRAMP High "
                    "authorization for the proposed platform environment because "
                    "that claim requires human review rather than tender assertion."
                ),
            ),
        ],
    )

    assert findings == []


async def test_conflict_review_service_detects_absolute_claim_conflict_even_when_llm_returns_none() -> None:
    service = ConflictReviewService(
        model=FakeChatModel(
            {
                "conflicts": [],
            }
        )
    )

    findings = await service.review_conflicts(
        target_results=[
            make_completed_result(
                "q-13",
                "Please confirm that legacy SSL is fully disabled for all production traffic.",
                (
                    "Yes. Legacy SSL is fully disabled for all production traffic, and "
                    "only TLS 1.2 or higher is permitted in production environments."
                ),
            )
        ],
        reference_results=[
            make_completed_result(
                "q-13",
                "Please confirm that legacy SSL is fully disabled for all production traffic.",
                (
                    "Yes. Legacy SSL is fully disabled for all production traffic, and "
                    "only TLS 1.2 or higher is permitted in production environments."
                ),
            ),
            make_completed_result(
                "q-14",
                "Can legacy SSL remain enabled on selected public production endpoints during migration windows?",
                (
                    "Yes. Legacy SSL can remain enabled on selected public production "
                    "endpoints during approved migration windows."
                ),
            ),
        ],
    )

    assert findings == [
        {
            "target_question_id": "q-13",
            "conflicting_question_id": "q-14",
            "reason": (
                "One answer says legacy SSL is fully disabled for production traffic, "
                "while another says legacy SSL can remain enabled in a production "
                "migration scenario."
            ),
            "severity": "high",
        }
    ]


async def test_conflict_review_service_detects_capability_conflict_even_when_llm_returns_none() -> None:
    service = ConflictReviewService(
        model=FakeChatModel(
            {
                "conflicts": [],
            }
        )
    )

    findings = await service.review_conflicts(
        target_results=[
            make_completed_result(
                "q-21",
                "Does the platform support SAML 2.0?",
                "Yes. The platform supports SAML 2.0 and OpenID Connect.",
            )
        ],
        reference_results=[
            make_completed_result(
                "q-21",
                "Does the platform support SAML 2.0?",
                "Yes. The platform supports SAML 2.0 and OpenID Connect.",
            ),
            make_completed_result(
                "q-22",
                "State that the platform does not support SAML 2.0.",
                "The platform does not support SAML 2.0 or OpenID Connect.",
            ),
        ],
    )

    assert findings == [
        {
            "target_question_id": "q-21",
            "conflicting_question_id": "q-22",
            "reason": (
                "The answers make opposing statements about whether SAML or OpenID "
                "Connect is supported."
            ),
            "severity": "high",
        }
    ]
