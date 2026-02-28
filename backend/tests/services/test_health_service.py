from app.schemas.health import HealthResponse
from app.services.health_service import get_health_status


def test_get_health_status_returns_health_response() -> None:
    assert get_health_status() == HealthResponse(status="ok")
