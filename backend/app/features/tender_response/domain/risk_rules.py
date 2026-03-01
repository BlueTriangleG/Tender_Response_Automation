"""Heuristic rules for catching obviously unsafe, unsupported, or inconsistent answers."""

HIGH_RISK_CERTIFICATION_TERMS = [
    "fedramp high",
    "fedramp",
    "soc 2 type ii",
    "soc 2",
    "iso 27001",
    "hipaa",
    "pci dss",
    "irap protected",
]

NEGATION_TERMS = [
    "do not",
    "does not",
    "not support",
    "not authorised",
    "not authorized",
    "not approved",
    "not included",
    "not used",
    "cannot",
    "can't",
    "cannot confirm",
    "can't confirm",
    "no evidence",
    "unsupported",
    "must not",
    "should not",
    "no ",
]

POSITIVE_TERMS = [
    "yes",
    "support",
    "supported",
    "available",
    "authorized",
    "authorised",
    "certified",
    "compliant",
    "included",
    "enforce",
]

STRONG_MODALITY_TERMS = [
    "must",
    "shall",
    "enforce",
    "strictly",
    "mandatory",
]

ABSOLUTE_CLAIM_TERMS = [
    "fully disabled",
    "all production traffic",
    "always",
    "never",
    "only ",
]

EXCEPTION_OR_CAVEAT_TERMS = [
    "however",
    "except",
    "exception",
    "exceptions",
    "rare migration",
    "migration window",
    "migration windows",
    "temporary exception",
    "temporary exceptions",
    "isolated transition",
    "may occur",
    "may allow",
]


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _window_around_term(text: str, term: str, *, padding: int = 48) -> str:
    index = text.find(term)
    if index == -1:
        return ""
    start = max(index - padding, 0)
    end = min(index + len(term) + padding, len(text))
    return text[start:end]


def _is_negated_or_refused(text: str) -> bool:
    return _contains_any(text, NEGATION_TERMS)


def _supports_term_positively(*, evidence_text: str, term: str) -> bool:
    if term not in evidence_text:
        return False
    return not _is_negated_or_refused(_window_around_term(evidence_text, term))


def detect_strong_modality_drift(
    *,
    question: str,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> bool:
    """Flag answers that strengthen mandatory language beyond the evidence."""

    lower_question = _normalize(question)
    lower_answer = _normalize(generated_answer)
    lower_alignment = _normalize(historical_alignment_answer)

    if not _contains_any(lower_question, STRONG_MODALITY_TERMS):
        return False
    if not _contains_any(lower_answer, STRONG_MODALITY_TERMS):
        return False
    if _is_negated_or_refused(lower_answer):
        return False
    return not _contains_any(lower_alignment, STRONG_MODALITY_TERMS)


def detect_high_risk_response(
    *,
    question: str,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> bool:
    """Flag answers that introduce sensitive certifications absent from evidence."""

    lower_question = _normalize(question)
    lower_answer = _normalize(generated_answer)
    lower_alignment = _normalize(historical_alignment_answer)

    if _is_negated_or_refused(lower_answer):
        return False

    for term in HIGH_RISK_CERTIFICATION_TERMS:
        if term not in lower_answer:
            continue
        if term not in lower_question and term not in lower_alignment:
            continue
        if not _supports_term_positively(evidence_text=lower_alignment, term=term):
            return True

    return detect_strong_modality_drift(
        question=question,
        generated_answer=generated_answer,
        historical_alignment_answer=historical_alignment_answer,
    )


def detect_inconsistent_response(
    *,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> bool:
    """Flag answers that contradict a positive historical reference with a negation."""

    if not historical_alignment_answer:
        return False

    lower_generated = _normalize(generated_answer)
    lower_alignment = _normalize(historical_alignment_answer)

    generated_negative = any(term in lower_generated for term in NEGATION_TERMS)
    alignment_positive = any(term in lower_alignment for term in POSITIVE_TERMS)

    return generated_negative and alignment_positive


def detect_absolute_claim_self_weakening(
    *,
    question: str,
    generated_answer: str,
) -> bool:
    """Flag answers that make an absolute claim and then immediately caveat it."""

    lower_question = _normalize(question)
    lower_answer = _normalize(generated_answer)

    if not _contains_any(lower_question, ABSOLUTE_CLAIM_TERMS):
        return False
    if not _contains_any(lower_answer, ABSOLUTE_CLAIM_TERMS):
        return False
    return _contains_any(lower_answer, EXCEPTION_OR_CAVEAT_TERMS)


def find_generation_validation_error(
    *,
    question: str,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> str | None:
    """Return a retryable validation error for unsupported claims or strengthened language."""

    if detect_high_risk_response(
        question=question,
        generated_answer=generated_answer,
        historical_alignment_answer=historical_alignment_answer,
    ):
        lower_question = _normalize(question)
        lower_answer = _normalize(generated_answer)
        if any(
            term in lower_answer and term in lower_question
            for term in HIGH_RISK_CERTIFICATION_TERMS
        ):
            return (
                "Generated answer makes an unsupported certification or compliance claim "
                "that is not positively evidenced in the references."
            )
        if _contains_any(lower_question, STRONG_MODALITY_TERMS) and _contains_any(
            lower_answer, STRONG_MODALITY_TERMS
        ):
            return (
                "Generated answer strengthens mandatory or enforcement language beyond "
                "what the references support."
            )
    if detect_absolute_claim_self_weakening(
        question=question,
        generated_answer=generated_answer,
    ):
        return (
            "Generated answer makes an absolute claim but then introduces exceptions "
            "or caveats that weaken it. Rewrite the answer so the claim and any limits "
            "are logically consistent."
        )
    return None
