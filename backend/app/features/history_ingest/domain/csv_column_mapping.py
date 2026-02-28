"""Deterministic CSV header matching for history-ingest QA files."""

import re
from dataclasses import dataclass

QUESTION_SYNONYMS = [
    "question",
    "questiontext",
    "prompt",
    "query",
    "tenderquestion",
    "customerquestion",
]
ANSWER_SYNONYMS = [
    "answer",
    "approvedanswer",
    "response",
    "suggestedanswer",
    "historicalanswer",
]
DOMAIN_SYNONYMS = [
    "domain",
    "category",
    "topicdomain",
    "practicearea",
]


def normalize_csv_header(header: str) -> str:
    """Normalize headers so visually similar labels compare consistently."""

    return re.sub(r"[^a-z0-9]+", "", header.strip().lower())


@dataclass(slots=True, eq=True)
class CsvColumnMappingResult:
    """Result of deterministic header matching before any LLM fallback."""

    question_col: str | None
    answer_col: str | None
    domain_col: str | None
    unresolved_targets: list[str]
    ambiguous_targets: list[str]

    @property
    def is_complete(self) -> bool:
        """Return True when every required target was resolved unambiguously."""

        return not self.unresolved_targets and not self.ambiguous_targets


def infer_csv_columns_from_headers(headers: list[str]) -> CsvColumnMappingResult:
    """Map raw CSV headers onto question/answer/domain targets."""

    question_col, question_ambiguous = _match_target(headers, QUESTION_SYNONYMS)
    answer_col, answer_ambiguous = _match_target(headers, ANSWER_SYNONYMS)
    domain_col, domain_ambiguous = _match_target(headers, DOMAIN_SYNONYMS)

    unresolved_targets: list[str] = []
    ambiguous_targets: list[str] = []

    if question_col is None and not question_ambiguous:
        unresolved_targets.append("question")
    if answer_col is None and not answer_ambiguous:
        unresolved_targets.append("answer")
    if domain_col is None and not domain_ambiguous:
        unresolved_targets.append("domain")

    if question_ambiguous:
        ambiguous_targets.append("question")
    if answer_ambiguous:
        ambiguous_targets.append("answer")
    if domain_ambiguous:
        ambiguous_targets.append("domain")

    return CsvColumnMappingResult(
        question_col=question_col,
        answer_col=answer_col,
        domain_col=domain_col,
        unresolved_targets=unresolved_targets,
        ambiguous_targets=ambiguous_targets,
    )


def _match_target(headers: list[str], synonyms: list[str]) -> tuple[str | None, bool]:
    """Return a unique matching header, or flag that multiple matches exist."""

    normalized_to_original = [(normalize_csv_header(header), header) for header in headers]
    candidates: list[str] = []

    for synonym in synonyms:
        matches = [
            original
            for normalized, original in normalized_to_original
            if normalized == synonym
        ]
        for match in matches:
            if match not in candidates:
                candidates.append(match)

    if len(candidates) == 1:
        return candidates[0], False
    if len(candidates) > 1:
        return None, True

    return None, False
