from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.health import router as health_router
from app.api.routes.history_ingest import router as history_ingest_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agent_router, tags=["agent"])
api_router.include_router(history_ingest_router, tags=["history-ingest"])
