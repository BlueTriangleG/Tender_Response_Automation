from fastapi import APIRouter

from app.agents.agent_manager import agent_manager
from app.core.config import settings
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix=settings.api_prefix)


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Send a message to the ReAct agent and return its response.

    The agent resolves tool calls (e.g. add_numbers) automatically before
    returning the final answer. Conversation history is preserved across
    requests that share the same session_id.
    """
    agent = agent_manager.get_agent(req.session_id, workflow_name=req.workflow_name)
    response = await agent.chat(req.message)
    return ChatResponse(response=response, session_id=req.session_id)
