from app.features.agent_chat.application.chat_use_case import AgentChatUseCase


def get_agent_chat_use_case() -> AgentChatUseCase:
    return AgentChatUseCase()
