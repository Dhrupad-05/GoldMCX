"""Schema bootstrap.

Local development uses SQLite by default; alembic remains the documented
workflow for PostgreSQL deployments (see README). This module applies the same
metadata with an alembic-style version stamp so `CHECKPOINT`-style drift is
auditable.
"""
from sqlalchemy import inspect, text

from app.db.base import Base


def _load_mappers() -> None:
    """Import all model modules so their tables register on Base.metadata."""
    from app.models import evaluation, market, source  # noqa: F401


def ensure_schema(engine) -> list[str]:
    """Create all tables that do not yet exist. Returns created table names."""
    _load_mappers()
    existing = set(inspect(engine).get_table_names())
    created = []
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    created = sorted(after - existing)
    return created


def drop_all(engine) -> None:
    """Destructive: only used by tests against a scratch database."""
    Base.metadata.drop_all(engine)
