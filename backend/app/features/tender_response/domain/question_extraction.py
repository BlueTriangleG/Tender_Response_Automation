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
    return "".join(ch for ch in header.strip().lower() if ch.isalnum() or ch == "_")


def find_first_matching_column(headers: list[str], candidates: list[str]) -> str | None:
    normalized_to_original = {normalize_header(header): header for header in headers}
    for candidate in candidates:
        matched = normalized_to_original.get(candidate)
        if matched:
            return matched
    return None
