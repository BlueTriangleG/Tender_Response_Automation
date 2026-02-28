"""Request models for the history-ingest API."""

from typing import Literal

from pydantic import BaseModel, Field


class HistoryIngestRequestOptions(BaseModel):
    """User-controlled options that shape ingestion behavior and response formatting."""

    output_format: Literal["json", "excel"] = "json"
    similarity_threshold: float = Field(default=0.72, ge=0.1, le=0.99)
