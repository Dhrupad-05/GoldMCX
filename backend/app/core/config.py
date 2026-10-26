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
    # the schema portable. Set DATABASE_URL to a postgresql+psycopg:// URL for
    # deployed environments (Supabase PostgreSQL is the shared/
    # runtime database). Production refuses to start on SQLite.
    database_url: str = "sqlite:///./storage/mcx_gold_dev.db"
    # Separate migrations URL (e.g. Supabase direct session vs pooled runtime) only
    # if explicitly needed; Alembic normally reuses database_url.
    migration_database_url: str | None = None

    # SQLAlchemy engine pool / statement controls (environment-backed).
    db_pool_size: int = 5
    db_pool_max_overflow: int = 5
    db_pool_recycle_s: int = 1800
    db_statement_timeout_ms: int = 15000
    db_lock_timeout_ms: int = 8000
    db_idle_in_transaction_timeout_ms: int = 30000

    # Distributed cache (Redis). Optional; unset means degraded/local bounded.
    redis_url: str | None = None

    # ---- Market-data providers (see docs/providers.md) --------------------
    # Enabled only with real entitlements; nothing is fabricated when missing.
    market_data_provider: str | None = None  # truedata | accelpix | mcx_direct
    public_market_data_display: bool = False  # licensing gate for public redistribution
    live_feed_enabled: bool = False           # dedicated feed worker on/off

    # TrueData Market Data API (login-id + password segments subscription).
    truedata_login_id: str | None = None
    truedata_password: str | None = None
    truedata_live_port: int = 8082        # production port per API spec
    truedata_live_url: str = "push.truedata.in"
    truedata_auth_url: str = "https://auth.truedata.in/token"
    truedata_history_url: str = "https://history.truedata.in"

    # AccelPix PIX API (api_token query auth; REST quote/history documented).
    accelpix_api_key: str | None = None
    accelpix_api_host: str = "apidata.accelpix.in"
    accelpix_scheme: str = "https"

    # MCX EOD bhavcopy (official daily reports).
    mcx_eod_enabled: bool = False
    mcx_bhavcopy_base: str = "https://www.mcxindia.com/backup/bhavcopy/BhavCopy_MCX_"

    # Freshness / session behaviour (seconds).
    live_feed_stale_after_s: int = 8
    live_quote_cache_ttl_s: int = 2
    mcx_session_tz: str = "Asia/Kolkata"

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
    def runtime_is_sqlite(self) -> bool:
        from sqlalchemy.engine import make_url

        return make_url(self.database_url).drivername.startswith("sqlite")

    @property
    def request_db_options(self) -> str:
        """Server-side per-session timeouts as a psycopg `options` string."""
        return (
            "-c statement_timeout={stmt} -c lock_timeout={lock} "
            "-c idle_in_transaction_session_timeout={idle}"
        ).format(
            stmt=self.db_statement_timeout_ms,
            lock=self.db_lock_timeout_ms,
            idle=self.db_idle_in_transaction_timeout_ms,
        )

    @property
    def market_provider_configured(self) -> bool:
        p = (self.market_data_provider or "").strip().lower()
        if p == "none" or p == "":
            return False
        if p == "truedata":
            return bool(self.truedata_login_id and self.truedata_password)
        if p == "accelpix":
            return bool(self.accelpix_api_key)
        return False  # mcx_direct requires dedicated licensed feed access

    @property
    def repo_root(self) -> Path:
        """Repository root (parent of backend/); hosts the root-level ml/ package."""
        return REPO_ROOT

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
