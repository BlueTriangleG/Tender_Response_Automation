"""Application-level health probe helpers."""

from app.features.health.schemas.responses import HealthResponse


def get_health_status() -> HealthResponse:
    """Return a minimal liveness response for uptime checks."""

    return HealthResponse(status="ok")
