from fastapi.testclient import TestClient

from app.main import app


def test_agent_chat_route_is_not_exposed() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/agent/chat",
        json={"session_id": "demo-session", "message": "hello"},
    )

    assert response.status_code == 404
