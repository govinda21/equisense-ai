from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    env: str = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    youtube_api_key: Optional[str] = Field(default=None, alias="YOUTUBE_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")

    # LLM provider + model (default: Ollama local)
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma3:4b", alias="OLLAMA_MODEL")

    # Generic LLM settings (optional overrides)
    llm_name: str = Field(default="gemma3:4b", alias="LLM_NAME")
    llm_host: str = Field(default="localhost", alias="LLM_HOST")
    llm_port: int = Field(default=11434, alias="LLM_PORT")

    http_timeout_seconds: int = Field(default=20, alias="HTTP_TIMEOUT_SECONDS")
    requests_per_minute: int = Field(default=60, alias="REQUESTS_PER_MINUTE")

    confidence_threshold: float = Field(default=0.7, alias="CONFIDENCE_THRESHOLD")

    # Langfuse observability
    langfuse_enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: Optional[str] = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: Optional[str] = Field(default=None, alias="LANGFUSE_HOST")

    # Resolve .env file to backend folder regardless of CWD
    _ENV_FILE = str(Path(__file__).resolve().parents[1] / ".env")
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # ignore unrelated env vars like LANGCHAIN_*
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
