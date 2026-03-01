"""Request models for tender-response generation."""

from pydantic import BaseModel, Field


class TenderResponseRequestOptions(BaseModel):
    """Per-request options that influence tender matching behavior."""

    session_id: str | None = None
    alignment_threshold: float = Field(default=0.6, ge=0.1, le=0.99)
