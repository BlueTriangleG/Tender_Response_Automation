from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_200_with_response_and_session_id() -> None:
    client = TestClient(app)
    mock_agent = MagicMock()
    mock_agent.chat = AsyncMock(return_value="The sum is 7.")

    with patch("app.api.routes.agent.agent_manager") as mock_manager:
        mock_manager.get_agent.return_value = mock_agent
        response = client.post(
            "/api/agent/chat",
            json={"message": "What is 3 + 4?", "session_id": "test-session"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "The sum is 7."
    assert data["session_id"] == "test-session"


def test_chat_passes_workflow_name_to_agent_manager() -> None:
    """workflow_name from the request body must reach agent_manager.get_agent
    so the correct workflow is loaded for the session."""
    client = TestClient(app)
    mock_agent = MagicMock()
    mock_agent.chat = AsyncMock(return_value="ok")

    with patch("app.api.routes.agent.agent_manager") as mock_manager:
        mock_manager.get_agent.return_value = mock_agent
        client.post(
            "/api/agent/chat",
            json={
                "message": "hello",
                "session_id": "test-session",
                "workflow_name": "tender_workflow",
            },
        )

    mock_manager.get_agent.assert_called_once_with(
        "test-session", workflow_name="tender_workflow"
    )


def test_chat_returns_422_when_message_is_missing() -> None:
    client = TestClient(app)
    response = client.post("/api/agent/chat", json={})
    assert response.status_code == 422
