"""Centralized application settings loaded from environment variables."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LANCEDB_URI = REPO_ROOT / "data" / "lancedb"


class Settings(BaseSettings):
    """Typed runtime configuration for the FastAPI backend."""

    app_name: str = "Pans Software Backend"
    api_prefix: str = "/api"
    lancedb_uri: str = str(DEFAULT_LANCEDB_URI)
    lancedb_qa_table_name: str = "qa_records"
    lancedb_document_table_name: str = "document_records"
    openai_chat_model: str = "gpt-4o-mini"
    openai_csv_column_model: str = "gpt-4o-mini"
    openai_tender_response_model: str = "gpt-5.2"
    openai_embedding_model: str = "text-embedding-3-small"
    tender_llm_request_timeout_seconds: float = 45.0
    tender_reference_assessment_retry_attempts: int = 2
    tender_conflict_review_timeout_seconds: float = 20.0
    tender_workflow_debug: bool = False
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )

    model_config = SettingsConfigDict(
        env_prefix="PANS_BACKEND_",
        case_sensitive=False,
    )


settings = Settings()
