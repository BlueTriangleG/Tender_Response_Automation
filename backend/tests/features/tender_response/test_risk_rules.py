from app.features.tender_response.domain.risk_rules import (
    detect_high_risk_response,
    detect_inconsistent_response,
    detect_strong_modality_drift,
    find_generation_validation_error,
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


def test_detect_inconsistent_response_ignores_reference_scope_caveat() -> None:
    assert (
        detect_inconsistent_response(
            generated_answer=(
                "Yes. The platform can return source citations, confidence cues, "
                "and workflow checkpoints for human review. (The provided references "
                "do not say whether these controls are mandatory for every "
                "procurement workflow.)"
            ),
            historical_alignment_answer=(
                "Yes. The platform can return source citations, confidence cues, "
                "and workflow checkpoints for human review when AI-assisted outputs "
                "inform business decisions."
            ),
        )
        is False
    )


def test_detect_inconsistent_response_ignores_negated_historical_positioning() -> None:
    assert (
        detect_inconsistent_response(
            generated_answer=(
                "No. We cannot commit to unlimited AI token usage across all "
                "business units on a fixed-fee basis."
            ),
            historical_alignment_answer=(
                "No standard approved position supports unlimited AI usage across "
                "all scenarios."
            ),
        )
        is False
    )


def test_detect_high_risk_response_allows_negated_certification_refusal() -> None:
    assert (
        detect_high_risk_response(
            question="Are you FedRAMP High authorised for this environment?",
            generated_answer=(
                "I cannot confirm FedRAMP High authorisation for this environment "
                "from the provided references."
            ),
            historical_alignment_answer=(
                "FedRAMP High authorization is not an approved claim and should be "
                "escalated for human review rather than asserted."
            ),
        )
        is False
    )


def test_detect_strong_modality_drift_flags_strengthened_language() -> None:
    assert (
        detect_strong_modality_drift(
            question="The platform MUST enforce TLS 1.2 or higher.",
            generated_answer="Yes. The platform strictly enforces TLS 1.2 or higher.",
            historical_alignment_answer="Yes. The platform supports TLS 1.2 or higher.",
        )
        is True
    )


def test_find_generation_validation_error_blocks_unsupported_certification_claim() -> None:
    assert (
        find_generation_validation_error(
            question="Are you FedRAMP authorised?",
            generated_answer="Yes, we are FedRAMP authorised.",
            historical_alignment_answer="We do not hold FedRAMP authorisation.",
        )
        == "Generated answer makes an unsupported certification or compliance claim that is not positively evidenced in the references."
    )


def test_find_generation_validation_error_blocks_unsupported_mandatory_language() -> None:
    assert (
        find_generation_validation_error(
            question="The supplier MUST enforce TLS 1.2 or higher for all production traffic.",
            generated_answer=(
                "Yes. We strictly enforce TLS 1.2 or higher for all production traffic."
            ),
            historical_alignment_answer="Yes. External production endpoints support TLS 1.2 or higher.",
        )
        == "Generated answer strengthens mandatory or enforcement language beyond what the references support."
    )


def test_find_generation_validation_error_blocks_absolute_claim_with_exception() -> None:
    assert (
        find_generation_validation_error(
            question=(
                "Please confirm that legacy SSL is fully disabled for all production "
                "traffic in the proposed environment."
            ),
            generated_answer=(
                "Yes. Legacy SSL is fully disabled for all production traffic. "
                "(Rare migration scenarios may allow limited temporary exceptions.)"
            ),
            historical_alignment_answer=(
                "Legacy SSL is not enabled for public production access, though "
                "isolated transition handling may be used in rare migration scenarios."
            ),
        )
        == "Generated answer makes an absolute claim but then introduces exceptions or caveats that weaken it. Rewrite the answer so the claim and any limits are logically consistent."
    )

