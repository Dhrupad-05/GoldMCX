"""Models for source registry, ingestion runs and raw staged rows."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_format: Mapped[str] = mapped_column(String(32), nullable=False)  # html|native_xls|csv|pdf|unknown
    source_class: Mapped[str] = mapped_column(String(32), nullable=False)
    # FUTURES_PRICE | ACTIVITY_REPORT | OPTIONS | CONTRACT_SPEC | ILLUSTRATIVE_DEMO | UNSUPPORTED
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    rejections: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("relative_path", "sha256", name="uq_source_files_path_sha"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="scan")  # scan|import
    counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    overall_status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    data_root: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class RawSourceRow(Base):
    """Immutable parsed staging record; never mutated after insert."""
    __tablename__ = "raw_source_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_id: Mapped[int] = mapped_column(
        Integer, nullable=True, index=True
    )  # FK added via migration script layer
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    # accepted | rejected | quarantined
    class_: Mapped[str] = mapped_column("source_class", String(32), nullable=False)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_file_id", "row_number", name="uq_raw_rows_file_row"),
        Index("ix_raw_rows_status", "validation_status"),
    )
