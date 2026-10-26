"""Layered cache: optional distributed Redis, in-process bounded fallback.

Design (docs/cache.md):
- Cache keys embed every result-shaping dimension plus a dataset version epoch.
- TTLs are configurable per namespace with small jitter to avoid synchronized expiry.
- Invalidation is published only AFTER the database commit succeeds; a rolled-back
  transaction never publishes new cached data.
- Redis unavailable -> degraded mode with a bounded in-process fallback in
  development/test only; production never silently replaces the shared cache
  with a process-local unbounded one.
- A single-flight guard prevents concurrent identical misses from hammering the
  database; a bounded wait degrades to a plain DB read.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Generic, TypeVar

logger = logging.getLogger("cache")

DATASET_VERSION = "v1"

T = TypeVar("T")


@dataclass
class TTL:
    dashboard: float = 12.0
    contracts: float = 60.0
    comparisons: float = 20.0
    signals: float = 15.0
    backtests: float = 90.0
    ingestion: float = 30.0
    live: float = 2.0


TTL_DEFAULTS = TTL()


def jitter(ttl: float) -> float:
    # Small deterministic-ish jitter (0..10%) to avoid synchronized expiry.
    factor = (int(time.time() * 10) % 11) / 100.0 + 0.9
    return max(1.0, ttl * factor)


class _Entry:
    __slots__ = ("value", "expires_at", "data_as_of", "cached_at")

    def __init__(self, value: Any, expires_at: float, data_as_of: Any, cached_at: float):
        self.value = value
        self.expires_at = expires_at
        self.data_as_of = data_as_of
        self.cached_at = cached_at


class _InProcessCache:
    """Bounded process-local fallback; never advertised as a distributed cache."""

    def __init__(self, max_entries: int = 512):
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str):
        with self._lock:
            e = self._entries.get(key)
            if e is None:
                return None
            if e.expires_at <= time.time():
                self._entries.pop(key, None)
                return None
            return (e.value, e.data_as_of, e.cached_at)

    def set(self, key: str, value: Any, expires_at: float, data_as_of: Any, cached_at: float) -> None:
        with self._lock:
            if len(self._entries) >= self._max:
                # Drop arbitrary stale entries first, then any key (bounded).
                stale = [k for k, e in self._entries.items() if e.expires_at <= time.time()]
                for k in stale:
                    self._entries.pop(k, None)
                if len(self._entries) >= self._max:
                    drop = next(iter(self._entries))
                    self._entries.pop(drop, None)
            self._entries[key] = _Entry(value, expires_at, data_as_of, cached_at)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)


_local_cache = _InProcessCache()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CacheLayer:
    """Shared cache facade; Redis is used when REDIS_URL is configured."""

    ttl: TTL = field(default_factory=lambda: TTL_DEFAULTS)
    redis: Any = None
    degraded: bool = False
    shared: bool = False
    _local_epoch: int = 1

    EPOCH_KEY: ClassVar[str] = "mcx:dataset_epoch"

    @classmethod
    def from_settings(cls) -> "CacheLayer":
        from app.core.config import get_settings

        s = get_settings()
        if s.redis_url:
            try:
                import redis  # soft dependency; install in envs that configure it

                client = redis.Redis.from_url(s.redis_url, decode_responses=True)
                client.ping()
                return cls(redis=client, shared=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("redis unavailable (%s); degraded cache mode", type(exc).__name__)
                return cls(degraded=True)
        if s.app_env not in ("development", "test"):
            logger.warning(
                "REDIS_URL not configured: shared cache disabled; bounded local fallback only."
            )
        return cls(degraded=True)

    # ---------------- key namespace -----------------------------------

    def current_epoch(self) -> int:
        """Dataset epoch shared across instances (Redis) or process-local."""
        if self.redis is not None:
            try:
                raw = self.redis.get(self.EPOCH_KEY)
                return int(raw) if raw else self._local_epoch
            except Exception:  # noqa: BLE001
                return self._local_epoch
        return self._local_epoch

    def bump(self) -> int:
        """Invalidate every derived read after a successful data commit.

        Must be called ONLY after the database transaction committed; rolled
        back writes must never publish invalidation.
        """
        if self.redis is not None:
            try:
                new = self.redis.incr(self.EPOCH_KEY)
                self._local_epoch = int(new)
                return self._local_epoch
            except Exception:  # noqa: BLE001
                logger.warning("redis epoch bump failed; invalidating locally")
        self._local_epoch += 1
        return self._local_epoch

    def key(self, endpoint: str, params: dict) -> str:
        basis = endpoint + "|" + json.dumps(params, sort_keys=True, default=str)
        return (
            f"mcx:v{DATASET_VERSION}:e{self.current_epoch()}:"
            f"{endpoint}:{hashlib.sha256(basis.encode()).hexdigest()[:32]}"
        )

    # ---------------- read/write --------------------------------------

    def get(self, key: str) -> tuple[Any, Any, Any] | None:
        """Return (value, data_as_of, cached_at) or None."""
        if self.redis is not None:
            try:
                raw = self.redis.get(key)
                if raw:
                    data = json.loads(raw)
                    return data.get("value"), data.get("data_as_of"), data.get("cached_at")
                return None
            except Exception:  # noqa: BLE001
                logger.warning("redis read failed; degraded fallback")
        return _local_cache.get(key)

    def set(self, key: str, value: Any, ttl: float, data_as_of: Any = None) -> None:
        now = utc_now_iso()
        ttl_eff = jitter(ttl)
        if self.redis is not None:
            try:
                self.redis.set(
                    key,
                    json.dumps({"value": value, "data_as_of": data_as_of, "cached_at": now}),
                    ex=max(1, int(ttl_eff)),
                )
                return
            except Exception:  # noqa: BLE001
                logger.warning("redis write failed; degraded fallback")
        _local_cache.set(key, value, ttl_eff, data_as_of, cached_at=time.time())

    def invalidate(self, *keys: str) -> None:
        if self.redis is not None:
            try:
                self.redis.delete(*keys)
            except Exception:  # noqa: BLE001
                logger.warning("redis invalidation failed")
        for k in keys:
            _local_cache.invalidate(k)

    # ---------------- single flight ------------------------------------
    # ClassVar so @dataclass does not treat these as per-instance fields.
    _flight_lock: ClassVar[threading.Lock] = threading.Lock()
    _flight: ClassVar[dict[str, threading.Event]] = {}

    def get_or_load(self, key: str, ttl: float, loader: Callable[[], T], data_as_of=None) -> T:
        hit = self.get(key)
        if hit is not None:
            _metrics["hits"] += 1
            return hit[0]
        _metrics["misses"] += 1
        with self._flight_lock:
            event = self._flight.get(key)
            owner = event is None
            if owner:
                event = threading.Event()
                self._flight[key] = event
        try:
            if not owner:
                # bounded wait: prevent stampede; degrade to load on timeout
                done = event.wait(2.0)
                if done:
                    settled = self.get(key)
                    if settled is not None:
                        return settled[0]
                return loader()
            value = loader()
            self.set(key, value, ttl, data_as_of=data_as_of)
            return value
        finally:
            if owner:
                with self._flight_lock:
                    self._flight.pop(key, None)
                event.set()


_metrics: dict[str, int] = {"hits": 0, "misses": 0}


def cache_metrics() -> dict:
    m = dict(_metrics)
    m["degraded"] = cache.degraded if cache is not None else True
    m["shared"] = cache.shared if cache is not None else False
    return m


cache: CacheLayer | None = None


def get_cache() -> CacheLayer:
    global cache
    if cache is None:
        cache = CacheLayer.from_settings()
    return cache
