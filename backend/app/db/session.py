"""Database engine/session handling. The URL is configuration, never code."""
import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
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


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        url = _resolve_url(os.environ.get("DATABASE_URL_OVERRIDE") or get_settings().database_url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        # 3306-style pool tuning is unnecessary for this workload; keep defaults.
        _engine = create_engine(url, future=True, connect_args=connect_args)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
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
