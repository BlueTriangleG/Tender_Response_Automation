"""Response models emitted by the tender-response workflow."""

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class QuestionFlags(BaseModel):
    """Boolean flags surfaced to clients for risky or inconsistent answers."""

    high_risk: bool = False
    inconsistent_response: bool = False
    has_conflict: bool = False


class QuestionRisk(BaseModel):
    """Risk classification attached to each generated question response."""

    level: Literal["high", "medium", "low"]
    reason: str | None = None


class QuestionMetadata(BaseModel):
    """Traceability metadata for the originating CSV row and alignment record."""

    source_row_index: int
    alignment_record_id: str | None = None
    alignment_score: float | None = None


class QuestionReference(BaseModel):
    """Historical QA or document-chunk reference returned to explain grounding decisions."""

    alignment_record_id: str
    reference_type: Literal["qa", "document_chunk"] = "qa"
    alignment_score: float | None = None
    source_doc: str | None = None
    matched_question: str
    matched_answer: str
    excerpt: str | None = None
    chunk_index: int | None = None
    used_for_answer: bool = False


class TenderQuestionResponse(BaseModel):
    """Per-question tender workflow result."""

    question_id: str
    original_question: str
    generated_answer: str | None = None
    domain_tag: str | None = None
    confidence_level: Literal["high", "medium", "low"] | None = None
    confidence_reason: str | None = None
    historical_alignment_indicator: bool
    status: Literal["completed", "unanswered", "failed"]
    grounding_status: Literal[
        "grounded",
        "partial_reference",
        "conflict",
        "insufficient_reference",
        "no_reference",
        "failed",
    ]
    flags: QuestionFlags = Field(default_factory=QuestionFlags)
    risk: QuestionRisk = Field(
        default_factory=lambda: QuestionRisk(level="low", reason=None)
    )
    metadata: QuestionMetadata
    references: list[QuestionReference] = Field(default_factory=list)
    error_message: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_confidence_fields(self) -> "TenderQuestionResponse":
        if self.confidence_reason == "":
            raise ValueError("confidence_reason must be null or a non-empty string.")
        if self.status == "unanswered":
            if self.confidence_level is not None:
                raise ValueError("unanswered responses must not set confidence_level.")
            if self.confidence_reason is not None:
                raise ValueError("unanswered responses must not set confidence_reason.")
        return self


class TenderResponseSummary(BaseModel):
    """Batch-level rollup for all questions in the uploaded CSV."""

    total_questions_processed: int
    flagged_high_risk_or_inconsistent_responses: int
    overall_completion_status: Literal[
        "completed",
        "completed_with_flags",
        "conflict",
        "unanswered",
        "partial_failure",
        "failed",
    ]
    completed_questions: int
    unanswered_questions: int
    failed_questions: int
    conflict_count: int = 0


class TenderResponseWorkflowResponse(BaseModel):
    """Top-level response returned by the tender-response endpoint."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    source_file_name: str
    total_questions_processed: int
    questions: list[TenderQuestionResponse]
    summary: TenderResponseSummary
