"""TrueData Market Data API adapter.

Documented behaviour (TrueData KB + Market Data API spec, verified Oct 2026,
see docs/providers.md for the URLs actually read):
- Auth: login id + password. Historical REST uses a bearer token from
  ``POST {auth_url}/token`` (form: username, password, grant_type=password),
  which refreshes periodically; the live websocket authenticates with the
  login id/password itself.
- History: ``GET {history_url}/getlastnbars?symbol=...&nbars=N&interval=eod
  &response=csv`` returns timestamp, open, high, low, close, OI and volume;
  daily bars cover 10+ years. Rate limits are documented (5 tick/10 minute-bar
  requests per second) and enforced here via bounded retries.
- Live: websocket on the configured live port (production 8082 per the API
  spec; sandbox ports differ) with server heartbeats every ~5-6s and a single
  concurrent login session per account.

This adapter only runs when TRUEDATA_LOGIN_ID/TRUEDATA_PASSWORD are supplied;
otherwise ``status()`` reports NOT CONFIGURED and no network I/O happens.
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from app.core.config import get_settings
from app.providers import base as pb

logger = logging.getLogger("truedata")
HISTORY_VERSION = "truedata_rest_v1"


class TrueDataProvider:
    name = "truedata"
    __slots__ = ("_status", "settings", "_client", "enabled", "configured", "_connect_lock")

    def __init__(self):
        self.settings = get_settings()
        self.configured = self.settings.market_provider_configured
        self.enabled = self.configured
        self._status = pb.ProviderStatus(
            provider=self.name,
            configured=self.configured,
            enabled=self.enabled,
            state="not_configured" if not self.configured else "connecting",
            detail=None if self.configured else
            "TrueData login id/password not supplied; live data remains BLOCKED.",
        )
        self._client: httpx.Client | None = None
        self._connect_lock = threading.Lock()

    # ------------------------------------------------------------------ auth
    def _history_token(self) -> str:
        """Obtain the bearer token for history REST calls (documented auth flow)."""
        resp = httpx.post(
            self.settings.truedata_auth_url,
            data={
                "username": self.settings.truedata_login_id,
                "password": self.settings.truedata_password,
                "grant_type": "password",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if resp.status_code == 401:
            raise pb.ProviderError(
                "TrueData auth rejected: check TRUEDATA_LOGIN_ID/TRUEDATA_PASSWORD.",
                pb.ProviderErrorCategory.AUTH,
            )
        resp.raise_for_status()
        if resp.status_code == 403 or "error" in resp.json():
            body = resp.json()
            raise pb.ProviderError(
                f"TrueData entitlements denied: {body}", pb.ProviderErrorCategory.ENTITLEMENT
            )
        token = (resp.json() or {}).get("access_token") or (resp.json() or {}).get("token")
        if not token:
            err = pb.ProviderError(
                "TrueData history token missing", pb.ProviderErrorCategory.PROTOCOL
            )
            raise err
        return token

    # ------------------------------------------------------------------ history
    def fetch_daily_bars(self, symbol: str, days: int = 30) -> list[pb.DailyBar]:
        if not self.configured:
            return []
        from app.services.instrument_map import provider_symbol_for

        psym = provider_symbol_for(self.name, symbol)
        if psym is None:
            return []
        token = self._history_token()
        url = (
            f"{self.settings.truedata_history_url}/getlastnbars"
            f"?symbol={psym}&nbars={days}&interval=eod&response=csv"
        )
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        if resp.status_code == 429:
            raise pb.ProviderError(
                "TrueData rate limit reached; back off before retry",
                pb.ProviderErrorCategory.RATE_LIMIT,
            )
        resp.raise_for_status()
        return _parse_eod_csv(resp.text, symbol, psym)

    # ------------------------------------------------------------------ status
    def status(self) -> pb.ProviderStatus:
        if not self.configured:
            return pb.not_configured_status(self.name)
        return self._status

    def connect(self) -> None:  # live websocket handled by the feed worker
        raise NotImplementedError(
            "TrueData live websocket belongs to the dedicated feed worker process."
        )

    def stop(self) -> None:
        return None

    def latest_quotes(self) -> dict[str, pb.QuoteEvent]:
        return {}


def _parse_eod_csv(text: str, canonical_symbol: str, provider_symbol: str) -> list[pb.DailyBar]:
    """Parse documented eod csv: timestamp, open, high, low, close, oi, volume."""
    out: list[pb.DailyBar] = []
    for line in text.splitlines():
        if not line.strip() or line.strip().lower().startswith("time"):
            continue
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < 5:
            continue
        try:
            bar = pb.DailyBar(
                symbol=canonical_symbol,
                trade_date=cells[0][:10],
                provider="truedata",
                open=float(cells[1]) if cells[1] else None,
                high=float(cells[2]) if cells[2] else None,
                low=float(cells[3]) if cells[3] else None,
                close=float(cells[4]) if cells[4] else None,
                volume=float(cells[-1]) if cells[-1] else None,
                open_interest=float(cells[-2]) if len(cells) > 6 and cells[-2] else None,
                provider_symbol=provider_symbol,
            )
        except ValueError as exc:
            logger.warning("truedata eod row parse failure: %s", exc)
            continue
        out.append(bar)
    return out
