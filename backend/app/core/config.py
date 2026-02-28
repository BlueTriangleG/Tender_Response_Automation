from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pans Software Backend"
    api_prefix: str = "/api"

    model_config = SettingsConfigDict(
        env_prefix="PANS_BACKEND_",
        case_sensitive=False,
    )


settings = Settings()
