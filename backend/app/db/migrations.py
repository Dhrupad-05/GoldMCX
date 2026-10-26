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
    from app.models import (  # noqa: F401
        evaluation, live, market, ml_registry, request, source,
    )


def ensure_schema(engine) -> list[str]:
    """Create all tables that do not yet exist. Returns created table names."""
    _load_mappers()
    existing = set(inspect(engine).get_table_names())
    created = []
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    created = sorted(after - existing)
    _apply_additive_drift(engine)
    return created


def _apply_additive_drift(engine) -> None:
    """Additively backfill columns/constraints create_all cannot alter.

    create_all only creates MISSING tables; late-added columns and unique
    constraints on existing tables performed by later migrations never appear
    in pre-migration dev DBs. This mirrors the current migration chain's
    ADDITIVE deltas only (never drops/rewrites).
    """
    insp = inspect(engine)
    is_sqlite = engine.dialect.name == "sqlite"

    # anomaly_scores.model_version (c9e86bc5b23f)
    cols = {c["name"] for c in insp.get_columns("anomaly_scores")}
    if "model_version" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE anomaly_scores ADD COLUMN model_version VARCHAR(64)"
            ))
            if not is_sqlite:
                conn.execute(text(
                    "CREATE INDEX ix_anomaly_scores_model_version "
                    "ON anomaly_scores (model_version)"
                ))

    # live_quote_events(provider, dedup_key) unique (c9e86bc5b23f).
    # Check by index name; on Postgres a named unique constraint is also
    # listed by get_indexes, on SQLite by its autoindex prefix.
    existing_names = {ix["name"] for ix in insp.get_indexes("live_quote_events")}
    have_dedup = any(
        n in existing_names
        for n in ("uq_live_quote_events_dedup", "sqlite_autoindex_live_quote_events_1")
    )
    if not have_dedup:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX uq_live_quote_events_dedup "
                "ON live_quote_events (provider, dedup_key)"
            ))


def drop_all(engine) -> None:
    """Destructive: only used by tests against a scratch database."""
    Base.metadata.drop_all(engine)
