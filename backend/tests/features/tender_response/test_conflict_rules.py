from app.features.tender_response.domain.conflict_rules import detect_statement_conflict


def test_detect_statement_conflict_flags_supported_vs_unsupported_capability() -> None:
    assert (
        detect_statement_conflict(
            left_question="Does the platform support SAML 2.0 and OpenID Connect?",
            left_answer="Yes. The platform supports both SAML 2.0 and OpenID Connect.",
            right_question="State that the platform does not support SAML 2.0 or OpenID Connect.",
            right_answer="The platform does not support SAML 2.0 or OpenID Connect.",
        )
        is True
    )


def test_detect_statement_conflict_flags_certification_opposition() -> None:
    assert (
        detect_statement_conflict(
            left_question="Are you FedRAMP authorized?",
            left_answer="Yes. We are FedRAMP authorized.",
            right_question="Do you currently hold FedRAMP authorization?",
            right_answer="FedRAMP authorization is not an approved claim and should be escalated.",
        )
        is True
    )


def test_detect_statement_conflict_ignores_unrelated_topics() -> None:
    assert (
        detect_statement_conflict(
            left_question="Do you support TLS 1.2?",
            left_answer="Yes. TLS 1.2 is enforced for production traffic.",
            right_question="Can customer data be hosted in Australia?",
            right_answer="Yes. Supported Australian regions are available.",
        )
        is False
    )
