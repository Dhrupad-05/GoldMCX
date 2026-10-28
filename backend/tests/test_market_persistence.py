"""EOD bar persistence and live-quote persistence: idempotency + dedup."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models.live import LiveQuoteEvent, ProviderDailyBar
from app.providers.base import DailyBar, QuoteEvent
from app.services.eod_persistence import persist_daily_bars


def _bar(**over):
    base = dict(
        symbol="GOLDM",
        trade_date="2026-01-05",
        provider="mcx_bhavcopy",
        open=70000.0,
        high=70150.0,
        low=69900.0,
        close=70075.0,
        volume=1234.0,
        open_interest=999.0,
        expiry_date="2026-01-30",
        provider_symbol="GOLDM JAN 2026",
        data_status="VERIFIED",
    )
    base.update(over)
    return DailyBar(**base)


# ---------------------------------------------------------------------------
# Daily bars: natural-key idempotent upsert + reconciliation
# ---------------------------------------------------------------------------

def test_rerunning_the_same_import_does_not_duplicate(session):
    r1 = persist_daily_bars(session, [_bar()])
    session.commit()
    r2 = persist_daily_bars(session, [_bar()])
    session.commit()

    assert r1["inserted"] == 1 and r2["inserted"] == 0
    n = session.execute(
        select(func.count()).select_from(ProviderDailyBar).where(
            ProviderDailyBar.symbol == "GOLDM",
            ProviderDailyBar.trade_date == datetime.strptime("2026-01-05", "%Y-%m-%d").date(),
        )
    ).scalar_one()
    assert n == 1


def test_revised_official_file_updates_the_same_record(session):
    persist_daily_bars(session, [_bar(close=70075.0)])
    session.commit()
    persist_daily_bars(session, [_bar(close=70200.0)])
    session.commit()

    row = session.execute(select(ProviderDailyBar)).scalar_one()
    assert row.close == Decimal("70200")  # revision applied, no duplicate row


def test_lower_priority_vendor_cannot_override_the_official_record(session):
    persist_daily_bars(session, [_bar(provider="mcx_bhavcopy", close=70075.0)])
    session.commit()
    r = persist_daily_bars(
        session, [_bar(provider="truedata", close=11111.0, trade_date="2026-01-05")]
    )
    session.commit()

    assert r["unchanged"] == 1 and r["updated"] == 0
    row = session.execute(select(ProviderDailyBar)).scalar_one()
    assert row.provider == "mcx_bhavcopy"  # official record stays authoritative
    assert row.close == Decimal("70075")


def test_user_vendor_after_official_new_date_jumps_its_lesser_priority_does_not_stomp(session):
    """Same trade date, same expiry: official record wins regardless of order."""
    persist_daily_bars(session, [_bar(provider="truedata", close=75000.0)])
    session.commit()
    persist_daily_bars(session, [_bar(provider="mcx_bhavcopy", close=70075.0)])
    session.commit()
    r = persist_daily_bars(session, [_bar(provider="truedata", close=22222.0)])
    session.commit()
    assert r["unchanged"] == 1

    row = session.execute(select(ProviderDailyBar)).scalar_one()
    assert row.provider == "mcx_bhavcopy" and row.close == Decimal("70075")


def test_malformed_and_quarantined_bars_are_rejected_with_reasons(session):
    r = persist_daily_bars(session, [
        _bar(data_status="QUARANTINED"),
        _bar(symbol="FAKE"),
        _bar(expiry_date=None, trade_date="2026-01-05"),
        _bar(open=None, close=None),
    ])
    assert r["rejected"] == 4
    assert r["inserted"] == 0


# ---------------------------------------------------------------------------
# Live quote events: deterministic dedup, no snapshot re-persistence
# ---------------------------------------------------------------------------

def _quote(**over):
    base = dict(
        canonical_symbol="GOLDM",
        provider_symbol="GOLDM JAN 2026",
        provider="truedata",
        event_time=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
        receive_time=datetime(2026, 1, 5, 10, 0, 1, tzinfo=timezone.utc),
        last_price=70010.0,
        bid=70008.0,
        ask=70012.0,
        expiry_date="2026-01-30",
    )
    base.update(over)
    return QuoteEvent(**base)


def _import_persist():
    import importlib

    from app.market import feed_worker

    importlib.reload(feed_worker)
    return feed_worker._batch_persist_quotes


def test_repeating_the_same_snapshot_persists_nothing_new(session):
    persist = _import_persist()
    ev = _quote()
    n1 = persist(session, [ev, ev])  # exact duplicates within the batch
    session.commit()
    n2 = persist(session, [_quote()])  # same source event on the next pass
    session.commit()

    assert n1 == 1
    assert n2 == 0
    n = session.execute(select(func.count()).select_from(LiveQuoteEvent)).scalar_one()
    assert n == 1


def test_new_tick_from_the_same_symbol_persists(session):
    persist = _import_persist()
    persist(session, [_quote(event_time=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc))])
    session.commit()
    n2 = persist(session, [_quote(event_time=datetime(2026, 1, 5, 10, 0, 1, tzinfo=timezone.utc),
                                  last_price=70021.0)])
    session.commit()
    assert n2 == 1


def test_dedup_key_is_deterministic_same_inputs_same_key():
    persist = _import_persist()
    a = persist.__globals__["_quote_dedup_key"](_quote(volume=None))
    b = persist.__globals__["_quote_dedup_key"](_quote(volume=None))
    assert a == b

    c = persist.__globals__["_quote_dedup_key"](_quote(last_price=42.0))
    assert c != a  # distinct source events must not collide


def test_database_enforces_unique_provider_dedup(session):
    persist = _import_persist()
    ev = _quote()
    persist(session, [ev])
    session.commit()

    from sqlalchemy.exc import IntegrityError

    second = _quote()
    ev_should_collide = LiveQuoteEvent(
        provider=second.provider,
        canonical_symbol=second.canonical_symbol,
        provider_symbol=second.provider_symbol,
        event_time=second.event_time,
        receive_time=second.receive_time,
        last_price=second.last_price,
        bid=second.bid,
        ask=second.ask,
        volume=second.volume,
        open_interest=second.open_interest,
        data_status=second.data_status,
        payload=second.payload,
        dedup_key=ev.dedup_key,
    )
    session.add(ev_should_collide)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
