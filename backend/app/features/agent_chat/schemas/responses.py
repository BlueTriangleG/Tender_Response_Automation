from pydantic import BaseModel


class ChatResponse(BaseModel):
    response: str
    session_id: str
