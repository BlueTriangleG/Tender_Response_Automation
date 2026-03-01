"""Core domain models for tender-question processing."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class TenderQuestion:
    """One tender question extracted from an uploaded CSV row."""

    question_id: str
    original_question: str
    declared_domain: str | None
    source_file_name: str
    source_row_index: int
    raw_row: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TenderTabularParseResult:
    """Questions extracted from a tender tabular upload."""

    source_file_name: str
    questions: list[TenderQuestion]


TenderCsvParseResult = TenderTabularParseResult


@dataclass(slots=True)
class HistoricalReference:
    """A historical QA row or document chunk retrieved as supporting evidence."""

    record_id: str
    question: str
    answer: str
    domain: str | None
    source_doc: str | None
    alignment_score: float
    reference_type: Literal["qa", "document_chunk"] = "qa"
    excerpt: str | None = None
    chunk_index: int | None = None


@dataclass(slots=True)
class HistoricalAlignmentResult:
    """Vector-search outcome for a single tender question."""

    matched: bool
    record_id: str | None
    question: str | None
    answer: str | None
    domain: str | None
    source_doc: str | None
    alignment_score: float | None
    references: list[HistoricalReference] = field(default_factory=list)


@dataclass(slots=True)
class ReferenceAssessmentResult:
    """Decision about whether retrieved references can ground an answer."""

    can_answer: bool
    grounding_status: str
    usable_reference_ids: list[str]
    reason: str
    supported_coverage_percent: int | None = None


@dataclass(slots=True)
class ResponseReviewResult:
    """Post-generation review metadata used to classify confidence and risk."""

    confidence_level: str
    confidence_reason: str
    risk_level: str
    risk_reason: str
    inconsistent_response: bool


@dataclass(slots=True)
class GroundedAnswerResult:
    """Single-call grounded generation output for an answer plus review metadata."""

    generated_answer: str
    confidence_level: str
    confidence_reason: str
    risk_level: str
    risk_reason: str
    inconsistent_response: bool
