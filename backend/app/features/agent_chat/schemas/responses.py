"""Response models for the agent-chat API."""

from pydantic import BaseModel


class ChatResponse(BaseModel):
    """Agent reply payload returned to API clients."""

    response: str
    session_id: str
