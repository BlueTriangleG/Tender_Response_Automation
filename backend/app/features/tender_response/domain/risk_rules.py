"""Heuristic rules for catching obviously unsafe or inconsistent answers."""

HIGH_RISK_CERTIFICATION_TERMS = [
    "fedramp",
    "soc 2",
    "iso 27001",
    "hipaa",
    "pci dss",
]

NEGATION_TERMS = [
    "do not",
    "does not",
    "not support",
    "cannot",
    "can't",
    "no ",
]

POSITIVE_TERMS = [
    "yes",
    "support",
    "supported",
    "available",
]


def detect_high_risk_response(
    *,
    question: str,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> bool:
    """Flag answers that introduce sensitive certifications absent from evidence."""

    lower_question = question.lower()
    lower_answer = generated_answer.lower()
    lower_alignment = (historical_alignment_answer or "").lower()

    for term in HIGH_RISK_CERTIFICATION_TERMS:
        if term in lower_question and term in lower_answer and term not in lower_alignment:
            return True

    return False


def detect_inconsistent_response(
    *,
    generated_answer: str,
    historical_alignment_answer: str | None,
) -> bool:
    """Flag answers that contradict a positive historical reference with a negation."""

    if not historical_alignment_answer:
        return False

    lower_generated = generated_answer.lower()
    lower_alignment = historical_alignment_answer.lower()

    generated_negative = any(term in lower_generated for term in NEGATION_TERMS)
    alignment_positive = any(term in lower_alignment for term in POSITIVE_TERMS)

    return generated_negative and alignment_positive
