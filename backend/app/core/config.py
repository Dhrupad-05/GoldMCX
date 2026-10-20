"""Centralized backend configuration (pydantic-settings)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor: this file is backend/app/core/config.py, so the repo root is three
# levels up and backend root is two levels up.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_prefix: str = "/api/v1"

    # No PostgreSQL server is required for local development; SQLAlchemy 2 keeps
    # the schema portable. Set DATABASE_URL to a postgresql+psycopg:// URL in
    # production.
    database_url: str = "sqlite:///./storage/mcx_gold_dev.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    mcx_data_dir: str = "../GoldMcx_Data"
    data_write_mode: str = "read_only"
    log_level: str = "INFO"
    import_max_file_mb: int = 50
    demo_fallback_enabled: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_root(self) -> Path:
        p = Path(self.mcx_data_dir)
        if not p.is_absolute():
            # Relative defaults are documented against the backend directory
            # (e.g. ../GoldMcx_Data - the folder beside backend/).
            p = (BACKEND_ROOT / p).resolve()
        return p.resolve()

    @property
    def storage_dir(self) -> Path:
        """Backend-owned writable storage (never inside the source root)."""
        d = BACKEND_ROOT / "storage"
        d.mkdir(parents=True, exist_ok=True)
        return d


@lru_cache
def get_settings() -> Settings:
    return Settings()
