"""Live-market routes.

- `GET /api/v1/market/live/status`: provider state WITHOUT credentials, plus
  freshness classification per canonical symbol.
- `GET /api/v1/market/live/quotes`: latest persisted provider quotes (durable).
- `GET /api/v1/market/live/stream`: SSE stream built on the feed worker's
  store; unconfigured deployments emit one `not_configured` event and close.
- `POST /api/v1/market/history/sync`: admin bhavcopy sync (gated).

No fabricated values in any path: an absent provider yields NOT CONFIGURED.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.ingestion import _ensure_admin
from app.core.config import get_settings
from app.core.errors import InvalidInput
from app.db.session import get_session
from app.market import feed_worker as feed_worker_mod
from app.providers import base as pb
from app.providers.base import QuoteStatus

router = APIRouter(prefix="/market", tags=["market-live"])


def _provider() -> pb.ProviderStatus:
    name = get_settings().market_data_provider
    if name == "truedata":
        from app.providers.truedata import TrueDataProvider

        return TrueDataProvider().status()
    if name == "accelpix":
        from app.providers.accelpix import AccelPixProvider

        return AccelPixProvider().status()
    return pb.not_configured_status("none")


def _quote_payload(event: pb.QuoteEvent, stale_after: float) -> dict:
    now = datetime.now(timezone.utc)
    event_t = event.event_time if event.event_time.tzinfo else event.event_time.replace(tzinfo=timezone.utc)
    age_s = (now - event_t).total_seconds()
    if age_s > stale_after:
        freshness = QuoteStatus.STALE.value
    elif age_s > stale_after / 2.0:
        freshness = QuoteStatus.DELAYED.value
    else:
        freshness = QuoteStatus.VERIFIED.value
    return {
        "symbol": event.canonical_symbol,
        "provider_symbol": event.provider_symbol,
        "provider": event.provider,
        "last_price": event.last_price,
        "bid": event.bid,
        "ask": event.ask,
        "volume": event.volume,
        "open_interest": event.open_interest,
        "event_time": _iso_z(event.event_time),
        "receive_time": _iso_z(event.receive_time),
        "age_seconds": round(age_s, 3),
        "freshness": freshness,
        "data_status": event.data_status,
        "expiry_date": event.expiry_date,
    }


def _iso_z(dt: datetime) -> str:
    return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()


@router.get("/live/status")
def live_status():
    status = _provider()
    s = get_settings()
    worker_state, quotes = feed_worker_mod.store.snapshot()
    latest_event_at = max(
        (q.receive_time for q in quotes.values()), default=None
    )
    fresh_quotes = (
        [dict(_quote_payload(q, s.live_feed_stale_after_s)) for _, q in sorted(quotes.items())]
        if worker_state == "connected" else []
    )
    return {
        "provider": {
            "name": status.provider,
            "configured": status.configured,
            "state": status.state,
            "error_category": status.error_category,
            "detail": status.detail,
            "subscriptions": status.subscriptions,
            "subscriptions_count": len(status.subscriptions),
        },
        "feed": {
            "worker_state": worker_state,
            "live_enabled": s.live_feed_enabled,
            "public_display_allowed": s.public_market_data_display,
            "stale_after_s": s.live_feed_stale_after_s,
            "quote_cache_ttl_s": s.live_quote_cache_ttl_s,
            "session_tz": s.mcx_session_tz,
        },
        "quotes": fresh_quotes,
        "last_event_at": _iso_z(latest_event_at) if latest_event_at else None,
        "public_display_gate": (
            "public display enabled: entitlement recorded in deployment config"
            if s.public_market_data_display
            else "public display disabled by configuration (licensing gate)"
        ),
    }


@router.get("/live/quotes")
def live_quotes(
    symbol: str | None = Query(default=None, pattern="^(GOLDM|GOLDTEN|GOLDGUINEA|GOLDPETAL)$"),
    since: datetime | None = None,
    session: Session = Depends(get_session),
):
    """Latest persisted provider quote per symbol (durable, not worker-local)."""
    from app.models.live import LiveQuoteEvent

    q = select(LiveQuoteEvent).order_by(LiveQuoteEvent.event_time.desc()).limit(400)
    if symbol:
        q = q.where(LiveQuoteEvent.canonical_symbol == symbol)
    if since:
        q = q.where(LiveQuoteEvent.event_time >= since)
    rows = session.execute(q).scalars().all()
    latest: dict[str, LiveQuoteEvent] = {}
    for r in rows:
        if r.canonical_symbol not in latest:
            latest[r.canonical_symbol] = r
    return {
        "quotes": [
            {
                "symbol": r.canonical_symbol,
                "provider": r.provider,
                "provider_symbol": r.provider_symbol,
                "event_time": _iso_z(r.event_time),
                "receive_time": _iso_z(r.receive_time),
                "last_price": float(r.last_price) if r.last_price else None,
                "bid": float(r.bid) if r.bid else None,
                "ask": float(r.ask) if r.ask else None,
                "volume": float(r.volume) if r.volume else None,
                "open_interest": float(r.open_interest) if r.open_interest else None,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "data_status": r.data_status,
            }
            for r in latest.values()
        ]
    }


@router.get("/live/stream")
def live_stream():
    s = get_settings()
    if not s.market_provider_configured:
        payload = {
            "type": "status",
            "status": QuoteStatus.NOT_CONFIGURED.value,
            "detail": "provider credentials absent; live stream unavailable",
        }
        return StreamingResponse(
            _sse_once(payload), media_type="text/event-stream",
            headers={"Cache-Control": "no-store"},
        )
    status = _provider()
    _, quotes = feed_worker_mod.store.snapshot()
    initial = {
        "type": "snapshot",
        "worker_state": feed_worker_mod.store.snapshot()[0],
        "quotes": {
            sym: _quote_payload(q, s.live_feed_stale_after_s)
            for sym, q in quotes.items()
        },
    }
    return StreamingResponse(
        _sse_loop(initial), media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


async def _sse_once(payload: dict):
    yield f"data: {json.dumps(payload)}\n\n"


async def _sse_loop(initial: dict):
    import asyncio

    store = feed_worker_mod.store
    yield f"data: {json.dumps(initial)}\n\n"
    last_seen: dict[str, str] = {}
    while True:
        try:
            await asyncio.wait_for(asyncio.to_thread(store.wait_for_update, None, 4.0), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        _, quotes = store.snapshot()
        for sym, q in quotes.items():
            payload = _quote_payload(q, get_settings().live_feed_stale_after_s)
            key = f"{payload['provider_symbol']}:{payload['event_time']}"
            if last_seen.get(sym) != key:
                last_seen[sym] = key
                yield f"data: {json.dumps({'type': 'quote', **payload})}\n\n"
        state, _ = store.snapshot()
        if state in ("not_configured", "error"):
            yield "data: " + json.dumps({"type": "status", "status": state}) + "\n\n"
            break


@router.post("/history/sync")
def sync_history(request: Request, days: int = Query(default=7, le=30),
                 session: Session = Depends(get_session)):
    """Admin-only official bhavcopy sync; disabled without explicit entitlement."""
    _ensure_admin(request)
    s = get_settings()
    if not s.mcx_eod_enabled:
        raise InvalidInput(
            "MCX EOD sync disabled in configuration (MCX_EOD_ENABLED). "
            "Enable only when the official channel is reachable and permitted.",
            status_code=409,
        )
    from app.providers.mcx_eod import sync_recent

    return sync_recent(days)


@router.get("/history/{symbol}")
def provider_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=730),
):
    """Provider-sourced daily bars for a contract; NOT CONFIGURED when absent."""
    name = get_settings().market_data_provider
    if not name or not get_settings().market_provider_configured:
        return {
            "symbol": symbol.upper(),
            "status": QuoteStatus.NOT_CONFIGURED.value,
            "bars": [],
            "note": "no provider credentials configured; no history available",
        }
    if name == "truedata":
        from app.providers.truedata import TrueDataProvider

        provider = TrueDataProvider()
    else:
        from app.providers.accelpix import AccelPixProvider

        provider = AccelPixProvider()
    try:
        bars = provider.fetch_daily_bars(symbol.upper(), days=days)
    except pb.ProviderError as exc:
        raise InvalidInput(
            f"provider history unavailable: {exc.category.value}", status_code=503
        ) from exc
    return {
        "symbol": symbol.upper(),
        "provider": name,
        "status": "ok" if bars else "no_bars",
        "bars": [
            {
                "trade_date": b.trade_date,
                "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                "volume": b.volume, "open_interest": b.open_interest,
                "expiry_date": b.expiry_date, "data_status": b.data_status,
            }
            for b in bars
        ],
    }
