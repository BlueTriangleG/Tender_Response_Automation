from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse
from app.services.health_service import get_health_status

router = APIRouter(prefix=settings.api_prefix)


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return get_health_status()
