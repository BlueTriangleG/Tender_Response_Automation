from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_name: str = "react_agent"
