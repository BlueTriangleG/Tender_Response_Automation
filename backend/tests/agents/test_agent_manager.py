from unittest.mock import MagicMock, patch

from app.agents.agent_manager import AgentManager


def test_get_agent_creates_new_agent_for_unknown_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        manager.get_agent("session-1")

    MockAgent.assert_called_once_with(session_id="session-1", workflow_name="react_agent")


def test_get_agent_returns_same_instance_for_same_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        first = manager.get_agent("session-1")
        second = manager.get_agent("session-1")

    assert first is second
    MockAgent.assert_called_once()  # constructed only once


def test_get_agent_forwards_workflow_name_to_agent() -> None:
    """workflow_name must be passed through to Agent so different sessions can
    use different workflows without creating a new manager."""
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        manager.get_agent("session-1", workflow_name="tender_workflow")

    MockAgent.assert_called_once_with(session_id="session-1", workflow_name="tender_workflow")


def test_get_agent_creates_separate_instances_for_different_sessions() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.side_effect = [MagicMock(), MagicMock()]
        a = manager.get_agent("session-a")
        b = manager.get_agent("session-b")

    assert a is not b


def test_get_agent_creates_separate_instances_for_same_session_different_workflow() -> None:
    """Same session_id with a different workflow_name must produce a distinct Agent.
    Without a composite key, the second call silently returns the first workflow's
    cached instance — a silent correctness bug."""
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.side_effect = [MagicMock(), MagicMock()]
        react = manager.get_agent("session-1", workflow_name="react_agent")
        tender = manager.get_agent("session-1", workflow_name="tender_workflow")

    assert react is not tender
