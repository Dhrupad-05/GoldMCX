"""Database engine/session handling. The URL is configuration, never code."""
import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_session_factory: sessionmaker[Session] | None = None


def _resolve_url(url: str) -> str:
    """Ensure the parent directory for local sqlite URLs exists."""
    from sqlalchemy.engine import make_url

    u = make_url(url)
    if u.drivername.startswith("sqlite") and u.database and u.database != ":memory:":
        p = Path(u.database)
        if not p.is_absolute() and not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
    return url


def _engine_options(url: str) -> dict:
    """URL-shaped engine options: pool sizing/timeouts for Postgres (Supabase)."""
    from sqlalchemy.engine import make_url

    u = make_url(url)
    if u.drivername.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}

    s = get_settings()
    connect_args: dict = {}
    # Enforce TLS and per-session timeouts server-side (psycopg options).
    if u.get_driver_name() == "psycopg":
        connect_args["options"] = s.request_db_options
        if "sslmode" not in url:
            connect_args.setdefault("sslmode", "require")
    options = {
        "pool_size": s.db_pool_size,
        "max_overflow": s.db_pool_max_overflow,
        "pool_recycle": s.db_pool_recycle_s,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    # Supabase transaction pooler (port 6543 or "pooler=true") cannot hold
    # server-side prepared statements across transactions; psycopg keeps its
    # own prepare threshold, which must be disabled in that mode.
    is_transaction_pooler = (
        (u.port == 6543) or ("pooler=true" in (url or ""))
    )
    if is_transaction_pooler:
        connect_args["prepare_threshold"] = 0
    return options


def get_engine():
    """Build the engine once; configuration and pool behaviour live in settings."""
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        requested = os.environ.get("DATABASE_URL_OVERRIDE") or settings.database_url
        # Shared/deployed environments must not silently fall back to SQLite.
        if settings.app_env not in ("development", "test") and requested.startswith("sqlite"):
            raise RuntimeError(
                "Non-development environments require PostgreSQL (DATABASE_URL). "
                "SQLite fallback is disabled outside development."
            )
        url = _resolve_url(requested)
        _engine = create_engine(url, future=True, **_engine_options(url))
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
        resolved = make_url(url)
        if resolved.drivername.startswith("sqlite") and settings.app_env in ("development", "test"):            # Local/dev bootstrap only: additively create missing tables.
            # PostgreSQL is always migrated by `alembic upgrade head` (§SETUP.md).
            from app.db.migrations import ensure_schema

            ensure_schema(_engine)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed on exit."""
    get_engine()
    assert _session_factory is not None
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database() -> tuple[bool, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "database reachable"
    except Exception as exc:  # noqa: BLE001 - readiness must not crash
        return False, f"database unreachable: {type(exc).__name__}"
