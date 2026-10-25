"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "ontology" / "schema"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://ontology:ontology@localhost:55432/ontology"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-v4.1-flash-1017"
    openrouter_fallback_model: str | None = None
    openrouter_site_url: str | None = None
    openrouter_site_name: str | None = None

    # Namespace used when minting object rids: ri.<namespace>.object.<uuid>
    rid_namespace: str = "liquor"


settings = Settings()
