"""Request models for tender-response generation."""

from uuid import uuid4

from pydantic import BaseModel, Field


class TenderResponseRequestOptions(BaseModel):
    """Per-request options that influence tender matching behavior."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    alignment_threshold: float = Field(default=0.82, ge=0.1, le=0.99)
