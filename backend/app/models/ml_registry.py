"""Trained-model registry: metadata, lineage and activation lifecycle.

The large .joblib artifact lives on disk (`ml/artifacts/` or a configured
shared path); this table is the durable, DB-backed source of truth for which
artifact version is CANDIDATE / ACTIVE / RETIRED / FAILED, its checksum and
its training lineage. Nothing here is a substitute for artifact validation:
the checksum and feature schema are re-verified when the artifact is loaded.
"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrainedModel(Base):
    """One registered trained-model artifact (joblib bundle) and its lineage."""

    __tablename__ = "ml_model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # daily | intraday
    mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_names: Mapped[list] = mapped_column(JSON, nullable=False)
    bundle_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    train_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    cutoff_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thresholds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    package_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    # candidate | active | retired | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        # Only one active artifact per scoring frequency.
        Index("ix_ml_model_registry_mode_status", "mode", "status"),
    )


def get_active_model(session, mode: str = "daily") -> TrainedModel | None:
    """Registered ACTIVE artifact row for a scoring frequency, or None."""
    return session.execute(
        select_active_stmt(mode)
    ).scalars().first()


def select_active_stmt(mode: str):
    from sqlalchemy import select

    return (
        select(TrainedModel)
        .where(TrainedModel.mode == mode, TrainedModel.status == "active")
        .order_by(TrainedModel.activated_at.desc())
    )
