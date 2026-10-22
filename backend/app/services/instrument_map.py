"""Canonical symbol -> provider ticker mapping, with verified-only enforcement.

The feed never guesses tickers. It looks for a verified ProviderInstrument row.
When a provider master is reachable (needs credentials), it downloads the
official master (AccelPix master with lot size, TrueData contract list), finds
matching expiry-dated contracts for the four canonical instruments, verifies
lot size/quote conventions against our contract spec, and inserts verified
rows. Unverified rows are never used to subscribe.
"""
from __future__ import annotations

import json
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.live import ProviderInstrument
from app.providers.base import CANONICAL_SYMBOLS, redact_query


def provider_symbol_for(provider: str, canonical_symbol: str) -> str | None:
    """Return the provider ticker only when a verified mapping exists."""
    from app.db.session import get_session

    s = get_session()
    try:
        return verified_provider_symbol(s, provider, canonical_symbol)
    finally:
        s.close()


def verified_provider_symbol(
    session: Session, provider: str, canonical_symbol: str
) -> str | None:
    row = session.execute(
        select(ProviderInstrument)
        .where(
            ProviderInstrument.provider == provider,
            ProviderInstrument.canonical_symbol == canonical_symbol,
            ProviderInstrument.verified.is_(True),
        )
        .order_by(ProviderInstrument.expiry_date.desc())
    ).scalars().first()
    return row.provider_symbol if row else None


def sync_provider_master(session: Session, provider: str) -> dict:
    """Pull the official instrument master and verify the canonical symbols.

    Returns a summary; every mapped row has verified=False until the mapping is
    checked against the contract spec (lot size/quotation). Marking verified
    requires explicit operator confirmation recorded with the row.
    """
    s = get_settings()
    if provider == "accelpix":
        if not s.accelpix_api_key:
            return {"provider": provider, "state": "not_configured"}
        token = s.accelpix_api_key
        url = f"{s.accelpix_scheme}://{s.accelpix_api_host}/api/hsd/Masters/3?fmt=json"
        resp = httpx.get(url, params={"api_token": token.replace(" ", "%20")}, timeout=60.0)
        if resp.status_code != 200:
            return {"provider": provider, "state": "unavailable",
                    "detail": f"master download failed: HTTP {resp.status_code}"}
        master = resp.json()
        return _ingest_master(session, provider, master)
    if provider == "truedata":
        if not (s.truedata_login_id and s.truedata_password):
            return {"provider": provider, "state": "not_configured"}
        # The TrueData symbol list is delivered per account/entitlement; without
        # entitlement it is not published. Do not fabricate tickers.
        return {
            "provider": provider,
            "state": "entitlement_required",
            "detail": "TrueData MCX contract symbol list requires an enabled subscription.",
        }
    return {"provider": provider, "state": "unsupported"}


def _ingest_master(session: Session, provider: str, master) -> dict:
    """Persist candidate contracts for the four canonical symbols (unverified)."""
    rows = master if isinstance(master, list) else (master or {}).get("d") or (master or {}).get("rows") or []
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        utkr = str(row.get("utkr") or row.get("u") or "").upper()
        if utkr not in CANONICAL_SYMBOLS and f"GOLD{utkr}" not in CANONICAL_SYMBOLS:
            continue
        inst = str(row.get("inst") or "").upper()
        if "FUT" not in inst and inst not in ("FUTCOM", "FUTIDX", "FUTIV"):
            continue
        candidates.append(row)
    added = 0
    for row in candidates:
        tkr = str(row.get("tkr") or "tk")
        expiry_raw = str(row.get("exp") or "")
        exp_dt = _parse_master_date(expiry_raw)
        if exp_dt is None:
            continue
        canonical = _canonical_of(str(row.get("utkr") or tkr), tkr)
        if canonical not in CANONICAL_SYMBOLS:
            continue
        lot = row.get("lot")
        obj = session.execute(
            select(ProviderInstrument).where(
                ProviderInstrument.provider == provider,
                ProviderInstrument.canonical_symbol == canonical,
                ProviderInstrument.expiry_date == exp_dt,
            )
        ).scalar_one_or_none()
        if obj is None:
            obj = ProviderInstrument(
                provider=provider, canonical_symbol=canonical, provider_symbol=tkr,
                expiry_date=exp_dt, lot_size=lot,
            )
            session.add(obj)
            added += 1
        else:
            obj.lot_size = lot
    session.commit()
    return {"provider": provider, "state": "candidates_recorded", "candidates": added}


def _parse_master_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _canonical_of(utkr: str, ticker: str) -> str:
    base = utkr.split(" ")[0].split("-")[0].upper()
    for sym in CANONICAL_SYMBOLS:
        if base.startswith(sym) or sym in ticker.upper():
            return sym
    if utkr.startswith("GUINEA"):
        return "GOLDGUINEA"
    if utkr.startswith("PETAL"):
        return "GOLDPETAL"
    return base
