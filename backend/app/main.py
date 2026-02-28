from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap.routers import api_router
from app.core.config import settings
from app.shared.db.lancedb_bootstrap import bootstrap_lancedb


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.lancedb = bootstrap_lancedb()
    app.state.lancedb_ready = True
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# The frontend runs on a separate Vite dev server during local development.
# Without explicit CORS headers the browser can show a 200 response in the
# network panel while still rejecting the JavaScript fetch as cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
