"""Market data construction: activity tables → normalized prices → pair features.

Everything produced here is explicitly PROVISIONAL: the source corpus has no
OHLC/settlement prices, so all values are activity-implied averages over all
traded contracts of a symbol on a date (no expiry dimension).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics.features import compute_pair_features
from app.analytics.normalize import (
    SYMBOL_DISPLAY,
    seed_contract_specs,
    spec_for,
)
from app.core.errors import NotFound
from app.core.pairs import PAIR_IDS
from app.models.market import ActivityDaily, GoldMarketBar, NormalizedPrice, OptionsDaily
from app.models.source import SourceFile


def rebuild_market_tables(session: Session) -> dict:
    """Seed spec master, derive normalized symbol-day prices, rebuild pair features."""
    specs_added = seed_contract_specs(session)

    total = {"specs_added": specs_added, "normalized_added": 0, "pairs": {}}
    q = select(ActivityDaily).order_by(ActivityDaily.symbol, ActivityDaily.trade_date)
    rows = session.execute(q).scalars().all()

    session.execute(delete(NormalizedPrice).where(
        NormalizedPrice.derivation_method == "activity_implied_value_per_lot"))

    # Dedup policy: one record per (symbol, date, instrument) - the more granular
    # 'detail' report is preferred over 'summary'; Summary/Detail are never added.
    chosen: dict[tuple[str, object, str], ActivityDaily] = {}
    for row in rows:
        if row.instrument != "FUTCOM":
            continue
        key = (row.symbol, row.trade_date, row.instrument)
        existing = chosen.get(key)
        if existing is None or (row.report_type == "detail" and existing.report_type == "summary"):
            chosen[key] = row

    current_symbol = None
    count_this = 0
    for row in sorted(chosen.values(), key=lambda r: (r.symbol, r.trade_date)):
        if row.symbol != current_symbol:
            current_symbol = row.symbol
            count_this = 0
        if row.lots is None or row.total_value_lakhs is None or row.lots <= 0 or float(row.total_value_lakhs) <= 0:
            continue
        spec = spec_for(session, row.symbol, row.trade_date)
        value_lakhs = float(row.total_value_lakhs)
        value_per_lot = value_lakhs * 100000.0 / float(row.lots)
        # Quoted price applies to quote_grams out of trading_unit_grams:
        quote_price = value_per_lot
        fine_grams = float(spec.quote_grams) * int(spec.purity_per_mille) / 1000.0
        lot_fine_grams = float(spec.trading_unit_grams) * int(spec.purity_per_mille) / 1000.0
        # price per quote basis scaled from the lot's value:
        price_per_quote = value_per_lot * float(spec.quote_grams) / float(spec.trading_unit_grams)
        normalized = price_per_quote / fine_grams

        session.add(NormalizedPrice(
            symbol=row.symbol,
            trade_date=row.trade_date,
            expiry_date=None,
            normalized_value=round(normalized, 6),
            raw_quoted_value=round(quote_price, 6),
            spec_version_id=spec.id,
            source_status="PROVISIONAL",
            derivation_method="activity_implied_value_per_lot",
            derivation_inputs={
                "lots": row.lots,
                "total_value_lakhs": value_lakhs,
                "value_per_lot_inr": round(value_per_lot, 4),
                "report_type": row.report_type,
                "instrument": row.instrument,
                "spec_valid_from": str(spec.valid_from),
                "verification_status": spec.verification_status,
            },
        ))
        count_this += 1
        total["normalized_added"] = total.get("normalized_added", 0) + 1
    session.commit()

    for pair_id in PAIR_IDS:
        summary = compute_pair_features(session, pair_id)
        total["pairs"][pair_id] = summary
    return total


def contract_inventory(session: Session) -> list[dict]:
    """Contract cards with data coverage/quality per symbol."""
    out = []
    for symbol in ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"):
        acts = session.execute(
            select(ActivityDaily).where(
                ActivityDaily.symbol == symbol,
                ActivityDaily.instrument == "FUTCOM",
                ActivityDaily.report_type == "detail",
            ).order_by(ActivityDaily.trade_date)
        ).scalars().all()
        if not acts:
            out.append({
                "symbol": symbol,
                "display_name": SYMBOL_DISPLAY.get(symbol, symbol),
                "status": "NO_DATA",
                "specs": [],
                "data_summary": {"detail_days": 0},
            })
            continue
        latest = acts[-1]
        count = len(acts)
        uniq_days = len({(a.trade_date, a.report_type) for a in acts})
        total_lots = sum(a.lots or 0 for a in acts)
        total_value = sum(float(a.total_value_lakhs or 0) for a in acts)
        value_per_lot = (total_value * 100000.0 / total_lots) if total_lots else None
        out.append({
            "symbol": symbol,
            "display_name": SYMBOL_DISPLAY.get(symbol, symbol),
            "status": "PROVISIONAL",
            "specs": [_spec_dict(session, symbol, latest.trade_date)],
            "data_summary": {
                "detail_days": count,
                "first_date": acts[0].trade_date.isoformat(),
                "last_date": latest.trade_date.isoformat(),
                "value_per_lot_inr": round(value_per_lot, 2) if value_per_lot else None,
            },
            "latest_quote_set": {
                "latest_date": latest.trade_date.isoformat(),
                "lots": latest.lots,
                "total_value_lakhs": float(latest.total_value_lakhs or 0),
                "note": "activity-implied, not a settlement price",
            },
            "coverage_note": (
                f"{uniq_days} date-wise activity days; no expiry-dated OHLC in the corpus "
                "→ series are symbol-level aggregates."
            ),
            "expiry_label": None,  # unknowable from this corpus
        })
    return out


def _spec_dict(session: Session, symbol: str, on_date: date) -> dict:
    spec = spec_for(session, symbol, on_date)
    return {
        "valid_from": spec.valid_from.isoformat(),
        "valid_to": spec.valid_to.isoformat() if spec.valid_to else None,
        "trading_unit_grams": float(spec.trading_unit_grams),
        "quote_grams": float(spec.quote_grams),
        "purity_per_mille": int(spec.purity_per_mille),
        "quote_rule": spec.quote_rule,
        "verification_status": spec.verification_status,
        "source_document_id": spec.source_document_id,
        "notes": spec.notes,
    }


def data_freshness(session: Session) -> dict:
    latest = session.execute(
        select(ActivityDaily).order_by(ActivityDaily.trade_date.desc()).limit(1)
    ).scalars().first()
    sf = session.execute(select(SourceFile).order_by(SourceFile.last_seen_at.desc()).limit(1)).scalars().first()
    opts = session.execute(select(OptionsDaily).order_by(OptionsDaily.trade_date.desc()).limit(1)).scalars().first()
    gold = session.execute(select(GoldMarketBar).order_by(GoldMarketBar.trade_date.desc()).limit(1)).scalars().first()
    return {
        "latest_activity_trade_date": latest.trade_date.isoformat() if latest else None,
        "latest_options_trade_date": opts.trade_date.isoformat() if opts else None,
        "latest_gold_context_trade_date": gold.trade_date.isoformat() if gold else None,
        "last_source_seen": sf.last_seen_at.isoformat() if sf else None,
        "note": "Activity-report freshness; no live feed exists in this deployment.",
    }
