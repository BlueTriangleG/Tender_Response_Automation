from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.agent import Agent


async def test_agent_chat_returns_last_message_content() -> None:
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="3+4"), AIMessage(content="The sum is 7.")]
        }
    )

    with patch("app.agents.agent.create_workflow", return_value=mock_workflow):
        agent = Agent(session_id="s1")
        result = await agent.chat("3+4")

    assert result == "The sum is 7."


async def test_agent_chat_passes_session_id_as_thread_id() -> None:
    """session_id must become thread_id in the LangGraph config so the
    MemorySaver checkpointer can store and restore state per session."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="ok")]}
    )

    with patch("app.agents.agent.create_workflow", return_value=mock_workflow):
        agent = Agent(session_id="my-session")
        await agent.chat("hello")

    _, call_kwargs = mock_workflow.ainvoke.call_args
    config = call_kwargs["config"]
    assert config["configurable"]["thread_id"] == "my-session"
