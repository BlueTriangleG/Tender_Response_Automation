from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.features.agent_chat.api.dependencies import get_agent_chat_use_case
from app.main import app


def test_chat_returns_200_with_response_and_session_id() -> None:
    client = TestClient(app)
    mock_use_case = MagicMock()
    mock_use_case.chat = AsyncMock(
        return_value={"response": "The sum is 7.", "session_id": "test-session"}
    )

    app.dependency_overrides[get_agent_chat_use_case] = lambda: mock_use_case
    try:
        response = client.post(
            "/api/agent/chat",
            json={"message": "What is 3 + 4?", "session_id": "test-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "The sum is 7."
    assert data["session_id"] == "test-session"


def test_chat_passes_workflow_name_to_agent_manager() -> None:
    """workflow_name from the request body must reach the use case request model."""
    client = TestClient(app)
    mock_use_case = MagicMock()
    mock_use_case.chat = AsyncMock(
        return_value={"response": "ok", "session_id": "test-session"}
    )

    app.dependency_overrides[get_agent_chat_use_case] = lambda: mock_use_case
    try:
        client.post(
            "/api/agent/chat",
            json={
                "message": "hello",
                "session_id": "test-session",
                "workflow_name": "tender_workflow",
            },
        )
    finally:
        app.dependency_overrides.clear()

    request = mock_use_case.chat.await_args.args[0]
    assert request.session_id == "test-session"
    assert request.workflow_name == "tender_workflow"


def test_chat_returns_422_when_message_is_missing() -> None:
    client = TestClient(app)
    response = client.post("/api/agent/chat", json={})
    assert response.status_code == 422
