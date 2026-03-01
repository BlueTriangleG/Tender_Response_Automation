"""Deterministic contradiction rules for historical references and generated answers."""

from __future__ import annotations

import re

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "their",
    "there",
    "about",
    "where",
    "have",
    "has",
    "does",
    "what",
    "when",
    "which",
    "will",
    "would",
    "should",
    "could",
    "through",
    "because",
    "only",
    "public",
    "private",
    "proposed",
    "please",
    "can",
    "cannot",
    "not",
    "you",
    "all",
    "across",
    "platform",
    "service",
    "services",
    "customer",
    "customers",
    "standard",
    "business",
    "support",
    "supports",
    "supported",
    "provide",
    "provides",
    "provided",
    "available",
    "approved",
    "claim",
    "claims",
    "confirm",
    "current",
    "currently",
    "included",
    "disabled",
    "enabled",
    "human",
    "evidence",
    "authority",
    "report",
    "reports",
    "reference",
    "references",
    "response",
    "responses",
    "review",
    "state",
    "tender",
    "whether",
}

_HIGH_SIGNAL_TOPIC_TOKENS = {
    "ssl",
    "tls",
    "saml",
    "openid",
    "fedramp",
    "hipaa",
    "irap",
    "australia",
    "hosting",
    "sovereign",
    "audit",
    "siem",
    "worm",
    "erasure",
    "pricing",
    "token",
    "tokens",
    "rbac",
    "rpo",
    "rto",
    "penetration",
    "nda",
}

_CONTRADICTION_PAIRS = [
    (("fully disabled", "disabled", "not enabled"), ("remain enabled", "enabled", "may be used")),
    (("supports", "support", "supported"), ("does not support", "do not support", "unsupported")),
    (("available", "generally available", "is available"), ("not available", "unavailable")),
    (
        ("authorized", "authorised", "certified", "compliant"),
        (
            "not authorized",
            "not authorised",
            "not certified",
            "not compliant",
            "cannot confirm",
            "should be escalated",
        ),
    ),
    (("included",), ("not included", "excluded")),
    (("hosted in", "hosting in", "regional hosting"), ("cannot be hosted", "not hosted in")),
]


def normalize_conflict_text(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def extract_topic_tokens(*texts: str) -> set[str]:
    combined = normalize_conflict_text(" ".join(texts))
    tokens = set(re.findall(r"[a-z0-9][a-z0-9+-]{2,}", combined))
    return {
        token
        for token in tokens
        if token not in _STOPWORDS and not token.isdigit()
    }


def shared_topic_tokens(*, left_question: str, left_answer: str, right_question: str, right_answer: str) -> set[str]:
    left_tokens = extract_topic_tokens(left_question, left_answer)
    right_tokens = extract_topic_tokens(right_question, right_answer)
    return left_tokens & right_tokens


def has_meaningful_topic_overlap(
    *,
    left_question: str,
    left_answer: str,
    right_question: str,
    right_answer: str,
) -> bool:
    overlap = shared_topic_tokens(
        left_question=left_question,
        left_answer=left_answer,
        right_question=right_question,
        right_answer=right_answer,
    )
    if not overlap:
        return False
    if overlap & _HIGH_SIGNAL_TOPIC_TOKENS:
        return True
    substantive_overlap = {token for token in overlap if len(token) >= 5}
    return len(substantive_overlap) >= 2


def detect_statement_conflict(
    *,
    left_question: str,
    left_answer: str,
    right_question: str,
    right_answer: str,
) -> bool:
    """Return True when two statements share a topic but assert opposing claims."""

    left_text = normalize_conflict_text(f"{left_question} {left_answer}")
    right_text = normalize_conflict_text(f"{right_question} {right_answer}")
    if not has_meaningful_topic_overlap(
        left_question=left_question,
        left_answer=left_answer,
        right_question=right_question,
        right_answer=right_answer,
    ):
        return False

    for positive_terms, negative_terms in _CONTRADICTION_PAIRS:
        left_positive = any(term in left_text for term in positive_terms)
        right_positive = any(term in right_text for term in positive_terms)
        left_negative = any(term in left_text for term in negative_terms)
        right_negative = any(term in right_text for term in negative_terms)
        if (left_positive and right_negative) or (right_positive and left_negative):
            return True

    return False
