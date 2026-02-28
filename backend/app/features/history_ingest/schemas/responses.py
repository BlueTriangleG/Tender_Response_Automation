"""Response models emitted by the history-ingest feature."""

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions


class ParsedFilePayload(BaseModel):
    """Structured representation of one uploaded file after parsing."""

    file_name: str
    extension: str
    content_type: str | None = None
    size_bytes: int
    parsed_kind: str
    raw_text: str
    structured_data: Any = None
    row_count: int | None = None
    warnings: list[str] = Field(default_factory=list)


class DetectedCsvColumns(BaseModel):
    """Resolved CSV header names required for QA normalization."""

    question_col: str
    answer_col: str
    domain_col: str


class ProcessedHistoryFileResult(BaseModel):
    """Outcome for one uploaded file within a batch ingest request."""

    status: Literal["processed", "failed"]
    payload: ParsedFilePayload | None = None
    error_code: str | None = None
    error_message: str | None = None
    detected_columns: DetectedCsvColumns | None = None
    ingested_row_count: int = 0
    failed_row_count: int = 0
    storage_target: str | None = None


class HistoryIngestResponse(BaseModel):
    """Aggregate response for a batch of uploaded history files."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    total_file_count: int
    processed_file_count: int
    failed_file_count: int
    request_options: HistoryIngestRequestOptions = Field(
        default_factory=HistoryIngestRequestOptions
    )
    files: list[ProcessedHistoryFileResult]
