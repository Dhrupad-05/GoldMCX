"""Market-data provider boundary.

Every provider adapter is production code against the vendor's documented
HTTP/WS interface. This module never fabricates observations: a configured
provider that cannot reach its endpoint produces explicit error states; an
unconfigured provider produces ``NOT CONFIGURED``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

CANONICAL_SYMBOLS = ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL")


class QuoteStatus(str, Enum):
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    DELAYED = "DELAYED"
    DISCONNECTED = "DISCONNECTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderErrorCategory(str, Enum):
    AUTH = "auth"
    ENTITLEMENT = "entitlement"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    PROTOCOL = "protocol"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


class ProviderError(Exception):
    """Classified provider failure; never carries credentials."""

    def __init__(self, message: str, category: "ProviderErrorCategory"):
        super().__init__(message)
        self.category = category


@dataclass
class QuoteEvent:
    canonical_symbol: str
    provider_symbol: str
    provider: str
    event_time: datetime
    receive_time: datetime
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    expiry_date: str | None = None
    dedup_key: str | None = None
    data_status: str = "VERIFIED"
    payload: dict | None = None


@dataclass
class DailyBar:
    symbol: str
    trade_date: str
    provider: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    open_interest: float | None
    expiry_date: str | None = None
    provider_symbol: str | None = None
    data_status: str = "VERIFIED"


@dataclass
class ProviderStatus:
    provider: str
    configured: bool
    enabled: bool
    state: str  # not_configured | connecting | connected | reconnecting | degraded | error
    error_category: str | None = None
    detail: str | None = None
    last_connected_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_event_at: datetime | None = None
    subscriptions: list[str] = field(default_factory=list)


class MarketDataProvider(Protocol):
    """Implementations validate settings and expose status without secrets."""

    name: str

    def status(self) -> ProviderStatus: ...

    def connect(self) -> None: ...

    def stop(self) -> None: ...

    def latest_quotes(self) -> dict[str, QuoteEvent]: ...

    def fetch_daily_bars(self, symbol: str, days: int = 30) -> list[DailyBar]: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def not_configured_status(name: str) -> ProviderStatus:
    return ProviderStatus(
        provider=name, configured=False, enabled=False, state="not_configured",
        detail="Credentials not supplied; live data remains unavailable.",
    )


def redact_query(url: str) -> str:
    """Scrub api_token/password values from any logged URL."""
    import re

    return re.sub(r"(api_token|password)=([^&]+)", r"\1=***", url)
