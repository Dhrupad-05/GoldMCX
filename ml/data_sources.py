"""Coordinated authorization-aware collection of configured market sources.

This module reuses the existing backend provider adapters and the shared EOD
persistence service - there is NO second vendor client here. Sources are only
touched when actually configured; nothing is fabricated when credentials,
entitlements or published files are absent.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings


def sync_official_history(session: Session, days: int = 10) -> dict:
    """Best-effort collection across configured/authorized sources.

    Returns per-source outcomes. MCX bhavcopy is the only zero-credential
    source; TrueData/AccelPix adapters run (with retries/backoff inside the
    adapters) only when their credentials exist. Failures never abort the
    whole run: each source reports its own status and reason.
    """
    s = get_settings()
    results: dict[str, dict] = {}

    # ---- MCX official EOD bhavcopy -----------------------------------
    if s.mcx_eod_enabled:
        from app.api.v1.routes.ingestion import ADMIN_TOKEN_HEADER  # noqa: F401
        from app.providers.mcx_eod import ProviderError, sync_recent

        try:
            rows = sync_recent(days=days, session=session)
            ok = [r for r in rows if r.get("status") == "ok"]
            results["mcx_bhavcopy"] = {
                "state": "ok" if ok else "no_published_files",
                "days": rows,
                "bars_persisted": sum(r.get("inserted", 0) + r.get("updated", 0) for r in ok),
            }
        except ProviderError as exc:
            results["mcx_bhavcopy"] = {"state": "unavailable", "detail": str(exc)}
    else:
        results["mcx_bhavcopy"] = {
            "state": "not_configured",
            "detail": "MCX_EOD_ENABLED=false; enable after verifying the official channel.",
        }

    # ---- TrueData / AccelPix licensed history ------------------------
    provider_name = (s.market_data_provider or "").strip().lower()
    if provider_name in ("truedata", "accelpix") and s.market_provider_configured:
        if provider_name == "truedata":
            from app.providers.truedata import TrueDataProvider

            provider = TrueDataProvider()
        else:
            from app.providers.accelpix import AccelPixProvider

            provider = AccelPixProvider()
        from app.services.eod_persistence import persist_daily_bars

        for symbol in ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"):
            try:
                bars = provider.fetch_daily_bars(symbol, days=days)
                persisted = persist_daily_bars(session, bars)
                session.commit()
                results.setdefault(provider_name, {"state": "ok", "symbols": {}})
                results[provider_name]["symbols"][symbol] = {"bars": len(bars), **persisted}
            except Exception as exc:  # noqa: BLE001 - one symbol never stops the run
                results.setdefault(provider_name, {"state": "partial", "symbols": {}})
                results[provider_name]["symbols"][symbol] = {
                    "state": "failed", "detail": f"{type(exc).__name__}: {exc}",
                }
        if results.get(provider_name, {}).get("symbols"):
            results[provider_name]["state"] = (
                "ok"
                if all(
                    v.get("state") != "failed" for v in results[provider_name]["symbols"].values()
                )
                else "partial"
            )
    else:
        results[provider_name or "none"] = {
            "state": "not_configured",
            "detail": "No licensed provider credentials; EOD-only mode.",
        }
    return results


def declare_source_window(days: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=days), today
