"""Response models for health endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Minimal health payload consumed by liveness checks."""

    status: str
