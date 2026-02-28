from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph

from app.agents.state.agent_state import AgentState
from app.agents.workflows.react_agent import create, route_after_agent


def _state(messages: list) -> AgentState:
    return AgentState(messages=messages, workflow_metadata={}, final_response=None, error=None)


def test_route_after_agent_returns_tools_when_last_message_has_tool_calls() -> None:
    tool_call = {"id": "c1", "name": "add_numbers", "args": {"a": 1, "b": 2}, "type": "tool_call"}
    state = _state([AIMessage(content="", tool_calls=[tool_call])])

    assert route_after_agent(state) == "tools"


def test_route_after_agent_returns_end_when_no_tool_calls() -> None:
    state = _state([AIMessage(content="The answer is 7.")])

    assert route_after_agent(state) == END


def test_create_returns_compiled_state_graph() -> None:
    mock_model = MagicMock()
    mock_model.bind_tools.return_value = mock_model

    workflow = create(model=mock_model)

    assert isinstance(workflow, CompiledStateGraph)
