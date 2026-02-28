from dataclasses import dataclass, field


@dataclass(slots=True)
class TenderQuestion:
    question_id: str
    original_question: str
    declared_domain: str | None
    source_file_name: str
    source_row_index: int
    raw_row: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TenderCsvParseResult:
    source_file_name: str
    questions: list[TenderQuestion]


@dataclass(slots=True)
class HistoricalAlignmentResult:
    matched: bool
    record_id: str | None
    question: str | None
    answer: str | None
    domain: str | None
    alignment_score: float | None
