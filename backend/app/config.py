"""Runtime settings, read only from environment variables (DESIGN.md §3.3)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # backend/.env, wherever the process starts (api, scripts, tests).
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

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
