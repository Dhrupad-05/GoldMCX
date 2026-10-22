"""AccelPix PIX API adapter (documented REST surface; see docs/providers.md).

Documented behaviour (support.accelpix.com KB, verified Oct 2026):
- Auth: every REST request carries the vendor-issued key as ``?api_token=...``
  (URL-encoded). Tokens are redacted from all logs.
- Quotes snapshot: ``POST {scheme}://{host}/api/fda/rest/quote?api_token=...``
  with a JSON array body of tickers; the response is an array of quote objects
  (``tkr, pr, bp/bq, ap/aq, vol, oi``).
- EOD history: ``GET .../api/fda/rest/{ticker}/{yyyymmdd}/{yyyymmdd}?api_token=``
  for the specific contract expiry; the master download with lot size is
  ``.../api/hsd/Masters/3?fmt=json``.

The vendor's live streaming path is the official Python SDK (``pix-apidata``).
The feed worker uses the SDK when installed and entitled; this adapter covers
the REST surface so history/quotes work without the SDK installed.
"""
from __future__ import annotations

import logging
import urllib.parse
from datetime import date

import httpx

from app.core.config import get_settings
from app.providers import base as pb

logger = logging.getLogger("accelpix")


class AccelPixProvider:
    name = "accelpix"

    def __init__(self):
        self.settings = get_settings()
        self.configured = self.settings.market_provider_configured
        self._base = f"{self.settings.accelpix_scheme}://{self.settings.accelpix_api_host}"

    # ------------------------------------------------------------------ utils
    def _token(self) -> str:
        if not self.configured:
            raise pb.ProviderError(
                "AccelPix api key not supplied", pb.ProviderErrorCategory.AUTH
            )
        return urllib.parse.quote(self.settings.accelpix_api_key or "")

    def _classify(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise pb.ProviderError(
                "AccelPix rejected the api_token:",
                pb.ProviderErrorCategory.ENTITLEMENT,
            )
        if resp.status_code == 429:
            raise pb.ProviderError(
                "AccelPix rate limit reached",
                pb.ProviderErrorCategory.RATE_LIMIT,
            )
        resp.raise_for_status()

    # ------------------------------------------------------------------ history
    def fetch_daily_bars(self, symbol: str, days: str = 30) -> list[pb.DailyBar]:
        if not self.configured:
            return []
        from app.services.instrument_map import provider_symbol_for

        psym = provider_symbol_for(self.name, symbol)
        if psym is None:
            return []
        from datetime import timedelta

        today = date.today()
        start = (today - timedelta(days=days)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        token = self._token()
        url = (
            f"{self._base}/api/fda/rest/{urllib.parse.quote(psym)}/{start}/{end}"
            f"?api_token={token}"
        )
        logger.debug("accelpix EOD request %s", pb.redact_query(url))
        resp = httpx.get(url, timeout=30.0)
        self._classify(resp)
        return _parse_accelpix_json(resp.json(), symbol, psym)

    def latest_quote_snapshot(self, provider_symbols: list[str]) -> list[dict]:
        """Documented POST /quote snapshot used for status-verified freshness."""
        if not self.configured or not provider_symbols:
            return []
        token = self._token()
        url = f"{self._base}/api/fda/rest/quote?api_token={token}"
        logger.debug("accelpix quote snapshot %s", pb.redact_query(url))
        resp = httpx.post(url, json=list(provider_symbols), timeout=15.0)
        self._classify(resp)
        return resp.json() or []

    def status(self) -> pb.ProviderStatus:
        if not self.configured:
            return pb.not_configured_status(self.name)
        return pb.ProviderStatus(
            provider=self.name, configured=True, enabled=True, state="connecting"
        )

    def connect(self) -> None:
        raise NotImplementedError("Live streaming belongs to the dedicated feed worker.")

    def stop(self) -> None:
        return None

    def latest_quotes(self) -> dict[str, pb.QuoteEvent]:
        return {}


def _parse_accelpix_json(data, canonical_symbol: str, provider_symbol: str) -> list[pb.DailyBar]:
    out: list[pb.DailyBar] = []
    rows = data if isinstance(data, list) else (data or {}).get("d") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            bar = pb.DailyBar(
                symbol=canonical_symbol,
                trade_date=str(row.get("dt") or row.get("date") or "")[:10],
                provider="accelpix",
                open=_f(row, ("o", "op")),
                high=_f(row, ("h", "hi")),
                low=_f(row, ("l", "lo")),
                close=_f(row, ("c", "cl")),
                volume=_f(row, ("v", "vol")),
                open_interest=_f(row, ("oi", "oî")) if "oi" in row else None,
                expiry_date=str(row.get("exp")) if row.get("exp") else None,
                provider_symbol=provider_symbol,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("accelpix bar parse failure: %s", exc)
            continue
        out.append(bar)
    return out


def _f(row: dict, keys) -> float | None:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return float(v)
    return None
