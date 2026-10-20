"""Contracts, market data and derived normalized/feature models."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractSpec(Base):
    """Effective-dated, versioned contract specification master."""
    __tablename__ = "contract_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # open-ended when NULL
    trading_unit_grams: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quote_grams: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    purity_per_mille: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_rule: Mapped[str] = mapped_column(String(32), nullable=False, default="standard_fine")
    source_document_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PROVISIONAL")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_contract_specs_symbol_from", "symbol", "valid_from"),
    )


class FuturesBar(Base):
    """Expiry-specific daily futures OHLC.

    The supplied corpus contains NO OHLC source, so rows here would come only
    from future bhavcopy imports. Never fabricated from activity data.
    """
    __tablename__ = "futures_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    close: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    volume_lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_row_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "symbol", "expiry_date", "trade_date", "source_priority",
            name="uq_futures_bars_natural",
        ),
        Index("ix_futures_bars_sym_date", "symbol", "trade_date"),
    )


class ActivityDaily(Base):
    """Activity report rows (lots + aggregate traded value), kept separate from OHLC."""
    __tablename__ = "activity_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False)  # FUTCOM | OPTFUT
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)  # detail | summary
    lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    avg_daily_turnover_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    premium_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    source_row_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")

    __table_args__ = (
        UniqueConstraint(
            "symbol", "trade_date", "instrument", "report_type",
            name="uq_activity_daily_natural",
        ),
        Index("ix_activity_daily_sym_date", "symbol", "trade_date"),
    )


class NormalizedPrice(Base):
    """Derived comparable per-fine-gram values; reproducible from source + spec version."""
    __tablename__ = "normalized_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    normalized_value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    raw_quoted_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    spec_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # PROVISIONAL | VERIFIED
    source_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PROVISIONAL")
    derivation_method: Mapped[str] = mapped_column(String(48), nullable=False)
    # activity_implied_value_per_lot | settlement_price | ...
    derivation_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "symbol", "trade_date", "derivation_method",
            name="uq_normalized_prices_natural",
        ),
        Index("ix_normalized_prices_sym_date", "symbol", "trade_date"),
    )


class PairFeature(Base):
    """Pairwise relative-value features; keyed by canonical pair and date."""
    __tablename__ = "pair_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_pair_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    expiry_left: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_right: Mapped[date | None] = mapped_column(Date, nullable=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    spread_pct: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)
    spread_change_pct: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    price_ratio: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    left_volume_lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    right_volume_lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    left_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    right_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="pf_v1")
    source_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PROVISIONAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "canonical_pair_id", "trade_date", "feature_version",
            name="uq_pair_features_natural",
        ),
        Index("ix_pair_features_pair_date", "canonical_pair_id", "trade_date"),
    )


class GoldMarketBar(Base):
    """Gold-market aggregate daily activity (GOLD files, 2005-2026), a context series.

    Kept separate from the four target symbols because the activity rollup covers
    the 1 kg GOLD contract(s) plus aggregate flows, not a single expiry.
    """
    __tablename__ = "gold_market_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    source_row_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "instrument", "report_type",
            name="uq_gold_market_bars_natural",
        ),
    )


class OptionsDaily(Base):
    """Options/OPTFUT activity rows - never admitted to futures series."""
    __tablename__ = "options_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    lots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    premium_value_lakhs: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    source_row_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="VERIFIED")

    __table_args__ = (
        UniqueConstraint(
            "symbol", "trade_date", "report_type",
            name="uq_options_daily_natural",
        ),
    )
