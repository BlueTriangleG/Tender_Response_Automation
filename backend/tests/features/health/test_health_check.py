from app.features.health.application.health_check import get_health_status
from app.features.health.schemas.responses import HealthResponse


def test_get_health_status_returns_health_response() -> None:
    assert get_health_status() == HealthResponse(status="ok")
