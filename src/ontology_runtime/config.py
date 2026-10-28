"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_ROOT = PROJECT_ROOT / "ontology"
#: Every domain is a directory under here, identified by its `domain.yaml`.
DOMAINS_DIR = ONTOLOGY_ROOT / "domains"
#: Definitions shared by all domains (agent bookkeeping types and actions).
PLATFORM_DIR = ONTOLOGY_ROOT / "platform"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Domain served when no `--domain` is given. Set with `ONTOLOGY_DOMAIN`.
    domain: str = Field(default="liquor", validation_alias="ONTOLOGY_DOMAIN")

    database_url: str = "postgresql+asyncpg://ontology:ontology@localhost:55432/ontology"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-v4.1-flash-1017"
    openrouter_fallback_model: str | None = None
    openrouter_site_url: str | None = None
    openrouter_site_name: str | None = None

    def database_url_for(self, domain: str) -> str:
        """Per-domain override (`DATABASE_URL_LIQUOR`) falling back to the shared URL.

        Each domain instance gets its own database; the override keeps a
        second domain from accidentally writing into the first one's tables.
        """
        override = os.environ.get(f"DATABASE_URL_{domain.upper()}")
        return override or self.database_url


settings = Settings()


def resolve_domain_dir(name: str) -> Path:
    """Locate `ontology/domains/<name>`, raising a readable error if absent."""
    directory = DOMAINS_DIR / name
    if not (directory / "domain.yaml").exists():
        available = (
            sorted(p.name for p in DOMAINS_DIR.iterdir() if p.is_dir())
            if DOMAINS_DIR.is_dir()
            else []
        )
        raise FileNotFoundError(
            f"unknown domain {name!r}; available: {', '.join(available) or '(none)'}"
        )
    return directory


def list_domain_dirs() -> list[Path]:
    if not DOMAINS_DIR.is_dir():
        return []
    return sorted(p for p in DOMAINS_DIR.iterdir() if (p / "domain.yaml").exists())
