from app.features.tender_response.domain.risk_rules import (
    detect_high_risk_response,
    detect_inconsistent_response,
)


def test_detect_high_risk_response_flags_unsupported_certification_claim() -> None:
    assert (
        detect_high_risk_response(
            question="Are you FedRAMP authorised?",
            generated_answer="Yes, we are FedRAMP authorised.",
            historical_alignment_answer=None,
        )
        is True
    )


def test_detect_inconsistent_response_flags_contradiction_with_history() -> None:
    assert (
        detect_inconsistent_response(
            generated_answer="We do not support SAML SSO.",
            historical_alignment_answer="Yes. We support SAML 2.0 single sign-on.",
        )
        is True
    )


def test_detect_inconsistent_response_allows_consistent_answer() -> None:
    assert (
        detect_inconsistent_response(
            generated_answer="Yes. We support SAML 2.0 single sign-on.",
            historical_alignment_answer="Yes. We support SAML 2.0 single sign-on.",
        )
        is False
    )
