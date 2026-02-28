from unittest.mock import MagicMock, patch

from app.agents.agent_manager import AgentManager


def test_get_agent_creates_new_agent_for_unknown_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        manager.get_agent("session-1")

    MockAgent.assert_called_once_with(session_id="session-1")


def test_get_agent_returns_same_instance_for_same_session() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.return_value = MagicMock()
        first = manager.get_agent("session-1")
        second = manager.get_agent("session-1")

    assert first is second
    MockAgent.assert_called_once()  # constructed only once


def test_get_agent_creates_separate_instances_for_different_sessions() -> None:
    manager = AgentManager()

    with patch("app.agents.agent_manager.Agent") as MockAgent:
        MockAgent.side_effect = [MagicMock(), MagicMock()]
        a = manager.get_agent("session-a")
        b = manager.get_agent("session-b")

    assert a is not b
