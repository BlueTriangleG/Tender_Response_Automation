from typing import Literal

from pydantic import BaseModel, Field


class HistoryIngestRequestOptions(BaseModel):
    output_format: Literal["json", "excel"] = "json"
    similarity_threshold: float = Field(default=0.72, ge=0.1, le=0.99)
