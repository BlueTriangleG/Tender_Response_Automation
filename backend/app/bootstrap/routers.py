from fastapi import APIRouter

from app.features.agent_chat.api.routes import router as agent_router
from app.features.health.api.routes import router as health_router
from app.features.history_ingest.api.routes import router as history_ingest_router
from app.features.tender_response.api.routes import router as tender_response_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agent_router, tags=["agent"])
api_router.include_router(history_ingest_router, tags=["history-ingest"])
api_router.include_router(tender_response_router, tags=["tender-response"])
