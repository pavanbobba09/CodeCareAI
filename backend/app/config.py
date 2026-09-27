"""Runtime settings, read only from environment variables (DESIGN.md §3.3)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://codecare:codecare@localhost:5432/codecare"

    # The LLM is set only by env vars. Never hardcode a provider or model name.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # CORS allows localhost:3000 plus this configured deployed origin.
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
