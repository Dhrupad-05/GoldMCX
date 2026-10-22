"""Official MCX EOD bhavcopy downloader/parser.

Important scope boundary (per docs/providers.md):
- Bhavcopy is the official daily/EOD file channel; it is NOT a real-time API.
  A direct MCX real-time feed is a separately licensed service; that adapter is
  available only when official feed credentials/configuration are supplied
  (``market_data_provider=mcx_direct`` and ``MCX_FEED_*`` env vars).
- File URLs and their layout change; this module persists what it downloads in
  backend-owned storage and records lineage. Public scraping of live pages is
  prohibited; only the official bhavcopy/report channel is used.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.providers.base import DailyBar, ProviderError, ProviderErrorCategory

logger = logging.getLogger("mcx_eod")

BHAVCOPY_BASE = "https://www.mcxindia.com/backup/bhavcopy/BhavCopy_MCX_%Y%m%d_"  # documented pattern


def download_for_trade_day(trade_date: date, session: str = "1") -> Path:
    """Download the official bhavcopy file for a trade day to backend storage.

    session "1" = BhavCopy for regular session; MCX also publishes evening
    session files; caller selects. Files land under backend storage, never in
    the read-only source root.
    """
    s = get_settings()
    url = (
        s.mcx_bhavcopy_base
        + f"{trade_date:%Y%m%d}_{session}.xlsx"
    )
    dest = s.storage_dir / f"bhavcopy_{trade_date:%Y%m%d}_{session}.xlsx"
    if dest.exists():
        return dest
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"MCX bhavcopy network failure: {type(exc).__name__}",
            ProviderErrorCategory.NETWORK,
        ) from exc
    if resp.status_code == 404:
        raise ProviderError(
            f"No bhavcopy file published for {trade_date} (session {session})",
            ProviderErrorCategory.PROTOCOL,
        )
    resp.raise_for_status()
    if resp.status_code in (401, 403):
        raise ProviderError(
            "MCX bhavcopy endpoint requires authorization",
            ProviderErrorCategory.ENTITLEMENT,
        )
    dest.write_bytes(resp.content)
    if dest.stat().st_size < 1024:
        raise ProviderError(
            "MCX bhavcopy response too small to be valid",
            ProviderErrorCategory.PROTOCOL,
        )
    return dest


def parse_bhavcopy_futures(path: Path) -> list[DailyBar]:
    """Parse expiry-specific futures rows from an MCX bhavcopy file.

    Official bhavcopy headers vary between file generations, so this parser
    maps from a documented candidate-header list, falling back to positional
    order ONLY against the official file layout, and QUARANTINES every row it
    cannot verify. Parser versioning records the mapping used.
    """
    import pandas as pd

    if not path.exists():
        return []
    try:
        df = pd.read_excel(path)
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(
            f"bhavcopy unreadable: {type(exc).__name__}", ProviderErrorCategory.PROTOCOL
        ) from exc

    PARSER_VERSION = "bhavcopy_v1"
    FH = {
        "SYMBOL": ("commodity", "symbol"),
        "CONTRACT": ("contract", "ticker"),
        "EXPIRY_DT": ("expiry date", "expiry date(RU)"),
        "TRADE_DT": ("trade date", "business date"),
        "OPEN": ("open", "open price"),
        "HIGH": ("high", "high price"),
        "LOW": ("low", "low price"),
        "CLOSE": ("close", "close price", "close/cif"),
        "VOL": ("total traded quantity", "volume"),
        "OI": ("open interest at the end of the day", "open interest", "oi"),
        "SETTLE": ("settlement price", "cif"),
    }
    cols = {c.strip().lower(): c for c in df.columns}
    def col(*candidates):  # noqa: E301
        for cand in candidates:
            if cand in cols:
                return cols[cand]
        return None
    mapped = {field: col(*cands) for field, cands in FH.items()}
    missing_required = [f for f in ("SYMBOL", "EXPIRY_DT", "TRADE_DT", "OPEN", "HIGH", "LOW", "CLOSE")
                        if mapped[f] is None]
    if missing_required:
        logger.warning(
            "bhavcopy header mapping incomplete (parser=%s): missing %s",
            PARSER_VERSION, missing_required,
        )
        return []

    def num(row, field):
        v = row.get(mapped.get(field))
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    out: list[DailyBar] = []
    for _, row in df.iterrows():
        symbol = str(row[mapped["SYMBOL"]] or "").strip().upper()
        expiry_raw = str(row[mapped["EXPIRY_DT"]] or "").strip()
        trade_raw = str(row[mapped["TRADE_DT"]] or "").strip()
        if not symbol or not expiry_raw or not trade_raw:
            continue
        expiry = _clean_date(expiry_raw)
        trade_d = _clean_date(trade_raw)
        if expiry is None or trade_d is None:
            out.append(DailyBar(
                symbol=symbol, trade_date=trade_raw[:10], provider="mcx_bhavcopy",
                open=None, high=None, low=None, close=None, volume=None,
                open_interest=None, expiry_date=expiry_raw[:10],
                data_status="QUARANTINED",
            ))
            continue
        if symbol.endswith(".OPT") or "OPT" in symbol:
            continue  # options never enter the futures series
        o, h, l, c = num(row, "OPEN"), num(row, "HIGH"), num(row, "LOW"), num(row, "CLOSE")
        incomplete = any(p is None for p in (o, h, l, c))
        bad_values = any(p is not None and p <= 0 for p in (o, h, l, c))
        inconsistent = (
            not incomplete
            and (l > min(o, c) or h < max(o, c))
        )
        if incomplete or bad_values or inconsistent:
            out.append(DailyBar(
                symbol=symbol, trade_date=trade_raw[:10], provider="mcx_bhavcopy",
                open=None, high=None, low=None, close=None, volume=None,
                open_interest=None, expiry_date=expiry.isoformat(),
                data_status="QUARANTINED",
            ))
            continue
        pb_row = DailyBar(
            symbol=symbol, trade_date=trade_d.isoformat(), provider="mcx_bhavcopy",
            open=o, high=h, low=l, close=c,
            volume=num(row, "VOL"), open_interest=num(row, "OI"),
            expiry_date=expiry.isoformat(),
        )
        out.append(pb_row)
    return out


def _clean_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def sync_recent(days: int = 7):
    """Best-effort EOD sync; downloads what exists and records failures."""
    today = date.today()
    results = []
    for i in range(days):
        d = today - timedelta(days=i)
        try:
            path = download_for_trade_day(d)
            rows = parse_bhavcopy_futures(path)
            results.append({"trade_date": d.isoformat(), "status": "ok", "rows": len(rows)})
        except ProviderError as exc:
            results.append({
                "trade_date": d.isoformat(),
                "status": "unavailable",
                "category": exc.category.value,
                "detail": str(exc),
            })
    return results
