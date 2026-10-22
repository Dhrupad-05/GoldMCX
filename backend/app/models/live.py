"""Live market-data provider models: instruments, quotes, daily bars, sessions.

Every row carries source lineage (provider, provider symbol, canonical symbol,
contract identity/expiry, event/receive timestamps and quality status). No
provider record is ever relabelled as an activity-derived observation and no
activity-derived observation is relabelled as live data.
"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderInstrument(Base):
    """Verified mapping canonical symbol -> provider ticker for one expiry contract."""
    __tablename__ = "provider_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    canonical_symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    provider_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    lot_size: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    quote_grams: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "provider", "canonical_symbol", "expiry_date", "provider_symbol",
            name="uq_provider_instruments_natural",
        ),
    )


class LiveQuoteEvent(Base):
    """One validated provider quote/tick event, persisted in bounded batches."""
    __tablename__ = "live_quote_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    canonical_symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    provider_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    receive_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    bid: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    ask: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    open_interest: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(96), nullable=True)

    __table_args__ = (
        Index("ix_live_quote_events_provider_time", "provider", "event_time"),
        Index("ix_live_quote_events_symbol_time", "canonical_symbol", "event_time"),
    )


class ProviderDailyBar(Base):
    """Provider-sourced or bhavcopy-sourced daily bar for a specific expiry contract."""
    __tablename__ = "provider_daily_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    open: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    close: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    volume: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    open_interest: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "symbol", "expiry_date", "trade_date", "data_status", "source_priority",
            name="uq_provider_daily_bars_natural",
        ),
        Index("ix_provider_daily_bars_sym_date", "symbol", "trade_date"),
    )


class ProviderSession(Base):
    """Durable record of feed-worker provider connection lifecycle events."""
    __tablename__ = "provider_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    # connecting | connected | reconnecting | disconnected | degraded | error
    error_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
