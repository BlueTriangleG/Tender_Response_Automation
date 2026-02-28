from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pans Software Backend"
    api_prefix: str = "/api"
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
