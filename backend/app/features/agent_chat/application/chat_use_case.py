"""Application service for session-based agent chat."""

from app.agents.agent_manager import AgentManager, agent_manager
from app.features.agent_chat.schemas.requests import ChatRequest
from app.features.agent_chat.schemas.responses import ChatResponse


class AgentChatUseCase:
    """Resolve an agent for the session and proxy the user message through it."""

    def __init__(self, manager: AgentManager | None = None) -> None:
        self._manager = manager or agent_manager

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Send a chat request to the selected workflow and wrap the reply."""

        agent = self._manager.get_agent(req.session_id, workflow_name=req.workflow_name)
        response = await agent.chat(req.message)
        return ChatResponse(response=response, session_id=req.session_id)
