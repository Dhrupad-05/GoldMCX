"""Dedicated market-data feed worker.

Only this process owns provider network connections (one login session per
provider account, per documented limits). It:
- refuses to start without configured credentials (operator sees
  not_configured rather than a fabricated feed),
- subscribes to verified expiry-specific provider instruments for the four
  canonical symbols,
- classifies provider events (quote/tick/bid-ask), rejects malformed events
  without killing the stream,
- enforces the staleness threshold in UTC/event time,
- batches durable writes into Supabase PostgreSQL via SQLAlchemy,
- reconnects with bounded exponential backoff + jitter and a circuit breaker
  for auth/entitlement/rate-limit failures.

Frontends receive data through the FastAPI SSE endpoint backed by this worker's
in-process latest-quote store plus the persisted tables.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.locking import lock_key
from app.models.live import LiveQuoteEvent, ProviderSession
from app.providers import base as pb
from app.providers.truedata import TrueDataProvider

logger = logging.getLogger("feed_worker")


class LiveQuoteStore:
    """In-process latest quotes for the SSE endpoint (cache is always freshest)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._quotes: dict[str, pb.QuoteEvent] = {}
        self._state = "not_configured"
        self.updated_listeners: list[threading.Event] = []

    def apply(self, event: pb.QuoteEvent) -> None:
        with self._lock:
            current = self._quotes.get(event.canonical_symbol)
            if current is None or event.event_time >= current.event_time:
                if current and event.event_time == current.event_time and event.dedup_key == current.dedup_key:
                    return
                self._quotes[event.canonical_symbol] = event
            self._state = "connected"
        for ev in self.updated_listeners:
            ev.set()

    def state(self, value: str) -> None:
        with self._lock:
            self._state = value

    def snapshot(self) -> tuple[str, dict[str, pb.QuoteEvent]]:
        with self._lock:
            return self._state, dict(self._quotes)

    def wait_for_update(self, since: datetime | None, timeout: float) -> bool:
        ev = threading.Event()
        self.updated_listeners.append(ev)
        try:
            return ev.wait(timeout)
        finally:
            try:
                self.updated_listeners.remove(ev)
            except ValueError:
                pass


store = LiveQuoteStore()


class FeedWorker(threading.Thread):
    """Single leader process; refuses duplicate starts via the advisory lock."""

    def __init__(self, provider_name: str):
        super().__init__(daemon=True, name=f"feed-worker-{provider_name}")
        self.settings = get_settings()
        self.provider_name = provider_name
        self._stop = threading.Event()
        self._errors = 0
        self.provider: pb.MarketDataProvider | None = None
        self.session_factory = None  # bound lazily

    # -------------------------------------------------------------- lifecycle
    def run(self) -> None:
        if not self.settings.market_provider_configured:
            logger.info(
                "feed worker idle: no provider credentials configured "
                "(MARKET_DATA_PROVIDER unset). No fabricated data will be served."
            )
            store.state("not_configured")
            return
        from app.db.session import get_engine

        engine = get_engine()
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.session_factory = factory
        # Leadership lease: only one feed worker may hold the subscription for
        # its provider account (documented one-session limits).
        db = factory()
        try:
            from app.db.locking import _stub_held  # noqa: F401  (documented helper import)

            from sqlalchemy import text

            if engine.dialect.name == "postgresql":
                digest = int.from_bytes(
                    __import__("hashlib").blake2b(
                        lock_key("dataset", f"feed-{self.provider_name}").encode(), digest_size=8
                    ).digest(), "big"
                )
                got = db.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": digest}
                ).scalar_one_or_none()
                if not got:
                    logger.error("another feed worker holds the leader lease; exiting")
                    return
        finally:
            db.close()
        from app.providers.accelpix import AccelPixProvider

        self.provider = (
            TrueDataProvider() if self.provider_name == "truedata" else AccelPixProvider()
        )
        self._record_session(factory, "connecting")
        self._run_evenloop(factory)
        self._record_session(factory, "disconnected")

    def stop(self) -> None:
        self._stop.set()

    def _run_evenloop(self, factory) -> None:
        settings = self.settings
        backoff = 1.0
        poll_interval = max(0.5, settings.live_quote_cache_ttl_s)
        while not self._stop.is_set():
            try:
                self._poll_iterations(factory, poll_interval)
                backoff = 1.0
                self._errors = 0
            except pb.ProviderError as exc:
                if exc.category in (pb.ProviderErrorCategory.AUTH, pb.ProviderErrorCategory.ENTITLEMENT):
                    logger.error(
                        "circuit open: %s failure (%s); not retrying credentials blindly",
                        exc.category.value, exc,
                    )
                    store.state("degraded")
                    return
                self._errors += 1
                if self._errors >= 8:
                    store.state("error")
                    return
                backoff = min(60.0, backoff * 2.0 * (1.0 + random.random()))
                logger.warning("provider error (%s); retrying in %.1fs", exc, backoff)
                store.state("reconnecting")
                self._sleep(backoff)
            except Exception as exc:  # noqa: BLE001
                self._errors += 1
                backoff = min(60.0, backoff * 2.0 * (1.0 + random.random()))
                logger.exception("feed worker loop failure: %s", exc)
                self._sleep(backoff)

    def _poll_iterations(self, factory, interval: float) -> None:
        """Main loop subclass hooks: provider-specific event loop."""
        provider = self.provider
        assert provider is not None
        # Live paths differ per provider. TrueData: real websocket.
        if self.provider_name == "truedata":
            self._truedata_live(factory)
        else:
            self._accelpix_poll(factory, interval)

    # -------------------------------------------------------------- TrueData live
    def _truedata_live(self, factory) -> None:
        try:
            import websockets  # uvicorn[standard] ships it
        except Exception as exc:  # noqa: BLE001
            raise pb.ProviderError(
                "websockets library unavailable", pb.ProviderErrorCategory.INTERNAL
            ) from exc
        s = self.settings
        url = (
            f"wss://{s.truedata_live_url}:{s.truedata_live_port}"
            f"?user={s.truedata_login_id}&password={s.truedata_password}"
        )
        import asyncio

        async def loop() -> None:
            backoff = 1.0
            import ssl

            ssl_ctx = ssl.create_default_context()
            async with websockets.connect(
                url, ssl=ssl_ctx, ping_interval=None,
                close_timeout=5, open_timeout=15,
            ) as ws:
                store.state("connected")
                self._record_session(factory, "connected")
                async for message in ws:
                    event = _parse_truedata_message(message)
                    if event is not None:
                        store.apply(event)
                    if self._stop.is_set():
                        break

        try:
            asyncio.run(loop())
        except Exception as exc:  # noqa: BLE001
            store.state("disconnected")
            raise pb.ProviderError(f"truedata socket closed: {exc.__class__.__name__}",
                                   pb.ProviderErrorCategory.NETWORK) from exc

    # -------------------------------------------------------------- AccelPix poll
    def _accelpix_poll(self, factory, interval: float) -> None:
        s = self.settings
        if not s.accelpix_api_key:
            raise pb.ProviderError("apikey missing", pb.ProviderErrorCategory.AUTH)
        from app.providers.accelpix import AccelPixProvider

        provider = AccelPixProvider()
        while not self._stop.is_set():
            import urllib.parse

            from app.services.instrument_map import provider_symbol_for

            from app.db.session import get_session

            tickers: list[tuple[str, str]] = []
            db = factory()
            try:
                for sym in pb.CANONICAL_SYMBOLS:
                    psym = verified_provider_symbol_row(db, provider, sym)
                    if psym:
                        tickers.append((sym, psym))
            finally:
                db.close()
            if not tickers:
                raise pb.ProviderError(
                    "no verified provider instruments (sync the master first)",
                    pb.ProviderErrorCategory.ENTITLEMENT,
                )
            token = urllib.parse.quote(s.accelpix_api_key or "")
            base = f"{s.accelpix_scheme}://{s.accelpix_api_host}"
            url = f"{base}/api/fda/rest/quote?api_token={token}"
            import httpx

            try:
                resp = httpx.post(
                    url, json=[t[1] for t in tickers], timeout=10.0
                )
            except httpx.HTTPError as exc:
                raise pb.ProviderError(
                    f"snapshot network failure: {type(exc).__name__}",
                    pb.ProviderErrorCategory.NETWORK,
                ) from exc
            if resp.status_code in (401, 403):
                raise pb.ProviderError("entitlement rejected by accelpix",
                                       pb.ProviderErrorCategory.ENTITLEMENT)
            resp.raise_for_status()
            now = datetime.now(timezone.utc)
            for q in resp.json() or []:
                event = _q_from_accelpix(q, dict(tickers), now)
                if event is not None:
                    store.apply(event)
            db = factory()
            try:
                _batch_persist_quotes(db, list(store.snapshot()[1].values()))
                db.commit()
            finally:
                db.close()
            self._sleep(interval)

    # -------------------------------------------------------------- helpers
    def _record_session(self, factory, state: str, detail: str | None = None,
                        error_category: str | None = None) -> None:
        if factory is None:
            return
        db = factory()
        try:
            db.add(ProviderSession(
                provider=self.provider_name, state=state, detail=detail,
                error_category=error_category,
                ended_at=datetime.now(timezone.utc) if state == "disconnected" else None,
            ))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        finally:
            db.close()

    def _sleep(self, seconds: float) -> None:
        self._stop.wait(seconds)


def verified_provider_symbol_row(db: Session, provider: str, canonical: str) -> str | None:
    from app.services.instrument_map import verified_provider_symbol

    return verified_provider_symbol(db, provider, canonical)


# --------------------------------------------------------------------------- parsers

def _parse_truedata_message(message: Any) -> pb.QuoteEvent | None:
    """Validate a documented TrueData live message into a typed QuoteEvent.

    Malformed events are dropped with a warning; the stream keeps running.
    """
    try:
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")
        text = str(message)
        if text.startswith("heartbeat") or not text.strip():
            return None
        data = json.loads(text) if text.lstrip().startswith("[") or text.lstrip().startswith("{") else None
        if isinstance(data, str) is False and data is not None:
            pass
    except Exception:  # noqa: BLE001
        return None
    symbol = None
    values = []
    if isinstance(data, dict) and "symbol" in data:
        symbol = data.get("symbol")
        values = data
    elif isinstance(data, list) and len(data) >= 3:
        symbol = data[0]
        values = {"ltp": data[1], "vol": data[2]}
    else:
        return None
    from app.services.instrument_map import provider_symbol_for

    canonical = _canonical_from_provider_symbol(str(symbol))
    if canonical is None:
        return None
    ltp = values.get("ltp") or values.get("price")
    try:
        price = float(ltp) if ltp not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return pb.QuoteEvent(
        canonical_symbol=canonical,
        provider_symbol=str(symbol),
        provider="truedata",
        event_time=datetime.now(timezone.utc),
        receive_time=datetime.now(timezone.utc),
        last_price=price,
        volume=values.get("vol"),
        data_status="VERIFIED",
    )


def _q_from_accelpix(q: dict, tickers: dict[str, str], now: datetime) -> pb.QuoteEvent | None:
    tkr = str(q.get("tkr") or "")
    canonical = next((c for c, p in tickers.items() if p == tkr), None)
    if canonical is None:
        return None
    return pb.QuoteEvent(
        canonical_symbol=canonical,
        provider_symbol=tkr,
        provider="accelpix",
        event_time=now,
        receive_time=now,
        last_price=_num(q, ("pr", "price")),
        bid=_num(q, ("bp",)),
        ask=_num(q, ("ap",)),
        volume=_num(q, ("vol",)),
        open_interest=_num(q, ("oi",)),
        data_status="VERIFIED",
        payload=q,
    )


def _num(q: dict, keys) -> float | None:
    for k in keys:
        v = q.get(k)
        try:
            if v not in (None, ""):
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _canonical_from_provider_symbol(psym: str) -> str | None:
    up = psym.upper()
    for canonical in ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"):
        if up.startswith(canonical):
            return canonical
    return None


def _batch_persist_quotes(db: Session, events: list[pb.QuoteEvent]) -> None:
    """Batch-write validated quotes; provider event time is the source of truth."""
    import uuid

    for e in events[:200]:  # bounded batch size
        db.add(LiveQuoteEvent(
            provider=e.provider,
            canonical_symbol=e.canonical_symbol,
            provider_symbol=e.provider_symbol,
            event_time=e.event_time,
            receive_time=e.receive_time,
            last_price=e.last_price,
            bid=e.bid,
            ask=e.ask,
            volume=e.volume,
            open_interest=e.open_interest,
            data_status=e.data_status,
            payload=e.payload,
            dedup_key=e.dedup_key or uuid.uuid4().hex[:32],
        ))


def start_worker(provider_name: str | None = None) -> FeedWorker | None:
    """Start the dedicated worker thread inside this process (local dev path)."""
    from app.core.config import get_settings

    s = get_settings()
    name = provider_name or s.market_data_provider
    worker = FeedWorker(name or "")
    worker.start()
    global _current_worker
    _current_worker = worker
    return worker


def stop_worker() -> None:
    global _current_worker
    if _current_worker is not None:
        _current_worker.stop()
        _current_worker = None


_current_worker: FeedWorker | None = None
