from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.agent import Agent


def _mock_module(content: str = "ok") -> tuple[MagicMock, MagicMock]:
    """Build a (mock_module, mock_workflow) pair for patching importlib."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content=content)]}
    )
    mock_module = MagicMock()
    mock_module.create.return_value = mock_workflow
    return mock_module, mock_workflow


async def test_agent_chat_returns_last_message_content() -> None:
    mock_module = MagicMock()
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="3+4"), AIMessage(content="The sum is 7.")]
        }
    )
    mock_module.create.return_value = mock_workflow

    with patch("app.agents.agent.importlib.import_module", return_value=mock_module):
        agent = Agent(session_id="s1")
        result = await agent.chat("3+4")

    assert result == "The sum is 7."


async def test_agent_chat_passes_session_id_as_thread_id() -> None:
    """session_id must become thread_id in the LangGraph config so the
    MemorySaver checkpointer can store and restore state per session."""
    mock_module, mock_workflow = _mock_module()

    with patch("app.agents.agent.importlib.import_module", return_value=mock_module):
        agent = Agent(session_id="my-session")
        await agent.chat("hello")

    _, call_kwargs = mock_workflow.ainvoke.call_args
    config = call_kwargs["config"]
    assert config["configurable"]["thread_id"] == "my-session"


async def test_agent_loads_workflow_by_name() -> None:
    """Agent must use importlib to load the workflow by name so new workflows
    can be added by dropping a file in workflows/ with no changes to Agent."""
    mock_module, _ = _mock_module()

    with patch("app.agents.agent.importlib.import_module", return_value=mock_module) as mock_import:
        Agent(session_id="s1", workflow_name="tender_workflow")

    mock_import.assert_called_once_with("app.agents.workflows.tender_workflow")
