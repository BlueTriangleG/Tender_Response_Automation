from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

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
