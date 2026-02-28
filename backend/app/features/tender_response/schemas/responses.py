from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class QuestionFlags(BaseModel):
    high_risk: bool = False
    inconsistent_response: bool = False


class QuestionMetadata(BaseModel):
    source_row_index: int
    alignment_record_id: str | None = None
    alignment_score: float | None = None


class QuestionReference(BaseModel):
    alignment_record_id: str
    alignment_score: float | None = None
    source_doc: str | None = None
    matched_question: str
    matched_answer: str


class TenderQuestionResponse(BaseModel):
    question_id: str
    original_question: str
    generated_answer: str | None = None
    domain_tag: str | None = None
    confidence_level: Literal["high", "medium", "low"] | None = None
    historical_alignment_indicator: bool
    status: Literal["completed", "failed"]
    flags: QuestionFlags = Field(default_factory=QuestionFlags)
    metadata: QuestionMetadata
    reference: QuestionReference | None = None
    error_message: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class TenderResponseSummary(BaseModel):
    total_questions_processed: int
    flagged_high_risk_or_inconsistent_responses: int
    overall_completion_status: Literal[
        "completed",
        "completed_with_flags",
        "partial_failure",
        "failed",
    ]
    completed_questions: int
    failed_questions: int


class TenderResponseWorkflowResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    source_file_name: str
    total_questions_processed: int
    questions: list[TenderQuestionResponse]
    summary: TenderResponseSummary
