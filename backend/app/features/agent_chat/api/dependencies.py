"""Dependency providers scoped to the agent-chat feature."""

from app.features.agent_chat.application.chat_use_case import AgentChatUseCase


def get_agent_chat_use_case() -> AgentChatUseCase:
    """Build an agent-chat use case for FastAPI handlers."""

    return AgentChatUseCase()
