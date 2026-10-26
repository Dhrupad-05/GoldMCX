"""Idempotent persistence of expiry-specific daily bars.

Natural record: (symbol, expiry_date, trade_date). Re-running an import for a
date/symbol/expiry payload must not create duplicates. If a higher-priority
source reports the same bar, the record carries the authoritative source while
the previous provider stays in lineage fields. Rows are never silently
blended: each bar keeps one provider's OHLC with its own source label.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.live import ProviderDailyBar
from app.providers.base import CANONICAL_SYMBOLS, DailyBar

# Deterministic reconciliation order (higher wins on the same natural key).
# mcx_bhavcopy is the official exchange record; vendor EOD blotters follow.
SOURCE_PRIORITY = {
    "mcx_bhavcopy": 100,
    "truedata": 50,
    "accelpix": 50,
}


def persist_daily_bars(session: Session, bars: list[DailyBar],
                       default_expiry: date | None = None) -> dict:
    """Upsert validated bars; returns inserted/updated/rejected counts + reasons."""
    counts = {"inserted": 0, "updated": 0, "rejected": 0, "unchanged": 0}
    reasons: dict[str, int] = {}
    for bar in bars:
        reason = _reject_reason(bar, default_expiry)
        if reason:
            counts["rejected"] += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        provider = bar.provider
        priority = SOURCE_PRIORITY.get(provider, 0)
        expiry = _as_date(bar.expiry_date) if bar.expiry_date else None
        trade = _as_date(bar.trade_date)
        existing = session.execute(
            select(ProviderDailyBar).where(
                ProviderDailyBar.symbol == bar.symbol,
                ProviderDailyBar.expiry_date == expiry,
                ProviderDailyBar.trade_date == trade,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(ProviderDailyBar(
                symbol=bar.symbol, expiry_date=expiry, trade_date=trade,
                provider=provider, provider_symbol=bar.provider_symbol,
                open=_dec(bar.open), high=_dec(bar.high), low=_dec(bar.low),
                close=_dec(bar.close), volume=_dec(bar.volume),
                open_interest=_dec(bar.open_interest),
                data_status=bar.data_status, source_priority=priority,
            ))
            counts["inserted"] += 1
            continue
        if priority < existing.source_priority:
            # Lower-priority source lost reconciliation to an official record.
            counts["unchanged"] += 1
            continue
        existing.provider = provider
        existing.provider_symbol = bar.provider_symbol
        existing.open = _dec(bar.open)
        existing.high = _dec(bar.high)
        existing.low = _dec(bar.low)
        existing.close = _dec(bar.close)
        existing.volume = _dec(bar.volume)
        existing.open_interest = _dec(bar.open_interest)
        existing.data_status = bar.data_status
        existing.source_priority = priority
        counts["updated"] += 1
    session.flush()
    counts["rejection_reasons"] = reasons
    return counts


def _reject_reason(bar: DailyBar, default_expiry: date | None) -> str | None:
    if bar.symbol not in CANONICAL_SYMBOLS:
        return f"non-canonical symbol {bar.symbol}"
    if bar.data_status == "QUARANTINED":
        return "quarantined bar"
    if not bar.trade_date:
        return "missing trade date"
    if not bar.expiry_date and default_expiry is None:
        # Expiry identity is mandatory: an expiry-less bar cannot enter a
        # contract-aware pipeline.
        return "missing expiry date"
    if bar.close in (None, 0) and bar.open in (None, 0):
        return "no usable prices"
    return None


def _as_date(raw: str | date) -> date | None:
    if isinstance(raw, date) and not isinstance(raw, type(date)):
        return raw
    from datetime import datetime

    raw = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _dec(v: float | Decimal | None) -> Decimal | None:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))
