from app.features.health.schemas.responses import HealthResponse


def get_health_status() -> HealthResponse:
    return HealthResponse(status="ok")
