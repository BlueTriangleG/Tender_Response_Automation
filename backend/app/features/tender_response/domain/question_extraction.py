"""Utilities for matching tender CSV columns to expected semantic roles."""

QUESTION_COLUMN_CANDIDATES = [
    "question",
    "question_text",
    "questiontext",
    "prompt",
    "query",
    "tender_question",
]

QUESTION_ID_COLUMN_CANDIDATES = [
    "question_id",
    "questionid",
    "id",
]

DOMAIN_COLUMN_CANDIDATES = [
    "domain",
    "category",
    "topic",
]


def normalize_header(header: str) -> str:
    """Normalize headers while preserving underscores that commonly appear in exports."""

    return "".join(ch for ch in header.strip().lower() if ch.isalnum() or ch == "_")


def find_first_matching_column(headers: list[str], candidates: list[str]) -> str | None:
    """Return the first candidate whose normalized name exists in the CSV headers."""

    normalized_to_original = {normalize_header(header): header for header in headers}
    for candidate in candidates:
        matched = normalized_to_original.get(candidate)
        if matched:
            return matched
    return None
