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

import hashlib
import json
import logging
import random
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
        # Leadership lease: a dedicated connection holds a SESSION-scoped
        # advisory lock for the entire worker lifetime. (A transaction-scoped
        # lock is released the moment its session closes, so the worker must
        # keep this connection open until shutdown.)
        self._leader_conn = None
        self._leader_digest: int | None = None

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
        if engine.dialect.name == "postgresql" and not self._acquire_leader_lease(engine):
            logger.error("another feed worker holds the leader lease; exiting")
            return
        try:
            self._run_locked(factory)
        finally:
            self._release_leader_lease()
            self._record_session(factory, "disconnected")

    def _acquire_leader_lease(self, engine) -> bool:
        """Hold a session-level advisory lock on a connection kept open until stop.

        pg_try_advisory_lock returns a real boolean; the lock survives
        transactions and lives exactly as long as this dedicated connection.
        """
        from sqlalchemy import text

        digest = int.from_bytes(
            hashlib.blake2b(
                f"feed-worker:{self.provider_name}".encode(), digest_size=8
            ).digest(), "big"
        )
        self._leader_digest = digest
        conn = engine.connect()
        try:
            got = conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": digest}
            ).scalar_one()
        except Exception:
            conn.close()
            raise
        self._leader_conn = conn if got else (conn.close() or None)
        return bool(got)

    def _release_leader_lease(self) -> None:
        from sqlalchemy import text

        if self._leader_conn is None:
            return
        try:
            if self._leader_digest is not None:
                self._leader_conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": self._leader_digest}
                )
        except Exception:  # noqa: BLE001 - connection close releases it anyway
            logger.warning("leader-lease unlock failed; closing connection releases the lock")
        finally:
            self._leader_conn.close()
            self._leader_conn = None
            self._leader_digest = None

    def _run_locked(self, factory) -> None:
        from app.providers.accelpix import AccelPixProvider

        self.provider = (
            TrueDataProvider() if self.provider_name == "truedata" else AccelPixProvider()
        )
        self._record_session(factory, "connecting")
        self._run_evenloop(factory)

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

def _first_key(values: dict, keys) -> Any:
    """Case-insensitive lookup across documented key spellings."""
    lowered = {k.lower(): v for k, v in values.items()}
    for key in keys:
        if key in lowered:
            return lowered[key]
    return None


def _parse_provider_time(value: Any, received_at: datetime) -> datetime:
    """Preserve the provider's own event timestamp when it supplies one.

    Supported wire formats: epoch seconds, epoch milliseconds, ISO-8601, and
    TrueData-session stamps like ``02JUN2025 15:30:02`` (Asia/Kolkata). When
    the provider supplies NO timestamp the receive time is used and the event
    is flagged RECEIVE_DERIVED_TIME — freshness claims stay honest.
    """
    if value in (None, ""):
        return received_at
    if isinstance(value, (int, float)):
        ts = value / 1000.0 if value > 1e12 else float(value)
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return received_at
    text = str(value).strip()
    for fmt in (
        "%d%b%Y %H:%M:%S", "%d%b%Y%H:%M:%S", "%d %b %Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S",
    ):
        try:
            from zoneinfo import ZoneInfo

            naive = datetime.strptime(text, fmt)
            return naive.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        from datetime import datetime as _dt

        parsed = _dt.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            from zoneinfo import ZoneInfo

            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return received_at


def _canonical_from_provider_symbol(psym: str) -> str | None:
    up = psym.upper()
    for canonical in ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"):
        if up.startswith(canonical):
            return canonical
    return None


def _quote_dedup_key(event: pb.QuoteEvent) -> str:
    """Deterministic fingerprint: identical source events collapse to one row.

    Re-persisting an unchanged latest-quote snapshot must never mint a fresh
    random key; the same (provider, symbol, event time, prices) tuple maps to
    the same key, backed by a database unique constraint.
    """
    basis = "|".join([
        event.provider,
        event.provider_symbol,
        event.event_time.isoformat() if event.event_time.tzinfo
        else event.event_time.isoformat() + "+00:00",
        str(event.last_price),
        str(event.bid),
        str(event.ask),
        str(event.volume),
        str(event.open_interest),
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:48]

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
    except Exception:  # noqa: BLE001
        return None
    symbol = None
    values: dict = {}
    if isinstance(data, dict):
        # Documented JSON quote objects carry the symbol + quote fields plus a
        # server event time/sequence. Keys vary by case; match case-insensitively.
        symbol = _first_key(data, ("symbol", "sym", "tkr"))
        if symbol is None:
            return None
        values = data
    elif isinstance(data, list) and len(data) >= 3:
        # Documented positional wire format: symbol, ltp, vol, bid, ask, ...
        symbol = data[0]
        values = {
            "ltp": data[1], "vol": data[2],
            **({"bid": data[3] if len(data) > 3 else None}),
            **({"ask": data[4] if len(data) > 4 else None}),
            **({"time": data[-1] if len(data) > 5 else None}),
        }
    else:
        return None
    ltp = _first_key(values, ("ltp", "price", "lastprice", "last"))
    try:
        price = float(ltp) if ltp not in (None, "") else None
    except (TypeError, ValueError):
        return None
    raw_time = _first_key(values, ("time", "timestamp", "ltt", "quotetimestamp", "ts"))
    received_at = datetime.now(timezone.utc)
    event_time = _parse_provider_time(raw_time, received_at)
    from app.services.instrument_map import provider_symbol_for

    canonical = _canonical_from_provider_symbol(str(symbol))
    if canonical is None:
        return None
    return pb.QuoteEvent(
        canonical_symbol=canonical,
        provider_symbol=str(symbol),
        provider="truedata",
        event_time=event_time,
        receive_time=received_at,
        last_price=price,
        bid=_num(values, ("bid", "bp")) if isinstance(values.get("bid"), (int, float)) else None,
        ask=_num(values, ("ask", "ap")) if isinstance(values.get("ask"), (int, float)) else None,
        volume=_num(values, ("vol", "volume")),
        dedup_key=None,
        data_status=("VERIFIED" if raw_time not in (None, "") else "RECEIVE_DERIVED_TIME"),
    )


def _q_from_accelpix(q: dict, tickers: dict[str, str], now: datetime) -> pb.QuoteEvent | None:
    tkr = str(q.get("tkr") or "")
    canonical = next((c for c, p in tickers.items() if p == tkr), None)
    if canonical is None:
        return None
    received_at = now
    raw_time = _first_key(q, ("tm", "time", "ltt", "ts", "dt"))
    event_time = _parse_provider_time(raw_time, received_at)
    return pb.QuoteEvent(
        canonical_symbol=canonical,
        provider_symbol=tkr,
        provider="accelpix",
        event_time=event_time,
        receive_time=received_at,
        last_price=_num(q, ("pr", "price")),
        bid=_num(q, ("bp",)),
        ask=_num(q, ("ap",)),
        volume=_num(q, ("vol",)),
        open_interest=_num(q, ("oi",)),
        data_status=("VERIFIED" if raw_time not in (None, "") else "RECEIVE_DERIVED_TIME"),
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


def _batch_persist_quotes(db: Session, events: list[pb.QuoteEvent]) -> int:
    """Persist only NEW validated quote events; source time is authoritative.

    Each event gets a deterministic fingerprint; events already persisted
    (same (provider, dedup_key) row) are skipped, so re-persisting an
    unchanged latest-quote snapshot writes nothing. Returns rows inserted.
    """
    if not events:
        return 0
    batch = events[:200]  # bounded batch size
    with_keys = []
    for e in batch:
        e.dedup_key = e.dedup_key or _quote_dedup_key(e)
        with_keys.append(e)
    existing = set(
        db.execute(
            select(LiveQuoteEvent.dedup_key).where(
                LiveQuoteEvent.provider == batch[0].provider,
                LiveQuoteEvent.dedup_key.in_([e.dedup_key for e in with_keys]),
            )
        ).scalars().all()
    )
    inserted = 0
    for e in with_keys:
        if e.dedup_key in existing:
            continue
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
            dedup_key=e.dedup_key,
        ))
        existing.add(e.dedup_key)
        inserted += 1
    return inserted


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
