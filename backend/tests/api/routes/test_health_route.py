from fastapi.testclient import TestClient

from app.main import app


def test_health_route_returns_ok_response() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_route_allows_frontend_dev_origin() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
