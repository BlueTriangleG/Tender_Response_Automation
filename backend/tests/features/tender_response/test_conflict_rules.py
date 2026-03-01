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


def test_detect_statement_conflict_ignores_pricing_vs_identity_false_positive() -> None:
    assert (
        detect_statement_conflict(
            left_question=(
                "Does the platform support SAML 2.0 or OpenID Connect single sign-on "
                "with role-based access control?"
            ),
            left_answer=(
                "Yes. The platform supports both SAML 2.0 and OpenID Connect single "
                "sign-on, and it provides role-based access control across tenant, "
                "workspace, and feature levels."
            ),
            right_question=(
                "Can you commit to fixed pricing for five years including unlimited "
                "AI token usage across all business units?"
            ),
            right_answer=(
                "We cannot commit to fixed pricing for five years that includes "
                "unlimited AI token usage across all business units."
            ),
        )
        is False
    )


def test_detect_statement_conflict_ignores_penetration_testing_vs_fedramp_false_positive() -> None:
    assert (
        detect_statement_conflict(
            left_question=(
                "Do you perform independent penetration testing and can evidence "
                "be shared during procurement under NDA?"
            ),
            left_answer=(
                "Yes. Independent penetration testing is performed at least annually "
                "and after material architectural changes. The provided references "
                "do not state whether penetration-test reports or other evidence can "
                "be shared under NDA, so this cannot be confirmed."
            ),
            right_question=(
                "Do you currently hold FedRAMP High authorization for the platform "
                "environment proposed in this tender?"
            ),
            right_answer=(
                "FedRAMP High authorization is not an approved claim in the current "
                "response library and should be referred for human review rather than "
                "asserted in a tender response."
            ),
        )
        is False
    )


def test_detect_statement_conflict_ignores_sample_pen_test_vs_fedramp_false_positive() -> None:
    assert (
        detect_statement_conflict(
            left_question=(
                "Do you perform independent penetration testing and can evidence "
                "be shared during procurement under NDA?"
            ),
            left_answer=(
                "Yes — independent penetration testing is performed at least "
                "annually and after material architectural changes; critical "
                "findings have tracked remediation. (The provided references do not "
                "state whether penetration-test reports or other test evidence can "
                "be shared during procurement under an NDA, so I cannot confirm "
                "evidence-sharing under NDA from these sources.)"
            ),
            right_question=(
                "Do you currently hold FedRAMP High authorization for the platform "
                "environment proposed in this tender?"
            ),
            right_answer=(
                "I cannot assert that we currently hold FedRAMP High authorization "
                "for the proposed platform environment. The provided references "
                "state that FedRAMP High authorization is not an approved claim in "
                "the current response library and should be referred for human "
                "review rather than asserted in a tender response (the references "
                "do not confirm whether an authorization actually exists)."
            ),
        )
        is False
    )


def test_detect_statement_conflict_ignores_penetration_testing_vs_pricing_false_positive() -> None:
    assert (
        detect_statement_conflict(
            left_question=(
                "Do you perform independent penetration testing and can evidence "
                "be shared during procurement under NDA?"
            ),
            left_answer=(
                "Yes. Independent penetration testing is performed at least annually "
                "and after material architectural change, with tracked remediation for "
                "critical findings. (The provided references do not state whether "
                "penetration-test evidence or reports can be shared during procurement "
                "under NDA, so I cannot confirm that from these references.)"
            ),
            right_question=(
                "Can you commit to fixed pricing for five years including unlimited "
                "AI token usage across all business units?"
            ),
            right_answer=(
                "I cannot commit to fixed pricing for five years that includes "
                "unlimited AI token usage across all business units. The provided "
                "historical references state that unlimited AI usage is not part of "
                "the standard approved commercial position and that fixed-fee terms "
                "historically applied only to defined base volumes, with excess usage "
                "and third-party AI consumption excluded. (The references do not "
                "provide authority or evidence to support committing to a five-year "
                "fixed-price term — that specific timeframe/commitment is unsupported "
                "by the provided references.)"
            ),
        )
        is False
    )
