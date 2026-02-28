from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions


class ParsedFilePayload(BaseModel):
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
    question_col: str
    answer_col: str
    domain_col: str


class ProcessedHistoryFileResult(BaseModel):
    status: Literal["processed", "failed"]
    payload: ParsedFilePayload | None = None
    error_code: str | None = None
    error_message: str | None = None
    detected_columns: DetectedCsvColumns | None = None
    ingested_row_count: int = 0
    failed_row_count: int = 0
    storage_target: str | None = None


class HistoryIngestResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    total_file_count: int
    processed_file_count: int
    failed_file_count: int
    request_options: HistoryIngestRequestOptions = Field(
        default_factory=HistoryIngestRequestOptions
    )
    files: list[ProcessedHistoryFileResult]
