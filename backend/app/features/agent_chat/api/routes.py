"""HTTP routes for the LangGraph-powered chat agent."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.features.agent_chat.api.dependencies import get_agent_chat_use_case
from app.features.agent_chat.application.chat_use_case import AgentChatUseCase
from app.features.agent_chat.schemas.requests import ChatRequest
from app.features.agent_chat.schemas.responses import ChatResponse

router = APIRouter(prefix=settings.api_prefix)


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    use_case: Annotated[AgentChatUseCase, Depends(get_agent_chat_use_case)] = None,
) -> ChatResponse:
    """Forward a chat request to the configured agent workflow."""

    return await use_case.chat(req)
