from fastapi import APIRouter

from app.core.config import settings
from app.features.health.application.health_check import get_health_status
from app.features.health.schemas.responses import HealthResponse

router = APIRouter(prefix=settings.api_prefix)


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return get_health_status()
