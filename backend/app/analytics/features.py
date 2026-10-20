"""Pair-feature computation over activity-implied normalized prices (PROVISIONAL).

Both legs of a pair are symbol-day aggregates (all traded contracts of that
symbol; this corpus has no expiry dimension). Alignment rule: observations must
share the same trade_date. Dates missing either leg produce no feature; the
skipped date count is returned and never forward-filled.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.pairs import pair_members
from app.models.market import NormalizedPrice, PairFeature

FEATURE_VERSION = "pf_v1"


def compute_pair_features(session: Session, pair_id: str) -> dict:
    """(Re)build pair_features for one canonical pair from normalized_prices."""
    left, right = pair_members(pair_id)
    left_rows = {
        r.trade_date: r
        for r in session.execute(
            select(NormalizedPrice).where(NormalizedPrice.symbol == left)
        ).scalars()
    }
    right_rows = {
        r.trade_date: r
        for r in session.execute(
            select(NormalizedPrice).where(NormalizedPrice.symbol == right)
        ).scalars()
    }

    session.execute(
        delete(PairFeature).where(
            PairFeature.canonical_pair_id == pair_id,
            PairFeature.feature_version == FEATURE_VERSION,
        )
    )

    common_dates = sorted(set(left_rows) & set(right_rows))
    missing_left = len(set(right_rows) - set(left_rows))
    missing_right = len(set(left_rows) - set(right_rows))

    added = 0
    prev_spread: float | None = None
    for d in common_dates:
        la, lr = left_rows[d], right_rows[d]
        a, b = float(la.normalized_value), float(lr.normalized_value)
        if a <= 0 or b <= 0:
            continue
        mid = (a + b) / 2.0
        spread_pct = (a - b) / mid * 100.0
        change = None if prev_spread is None else round(spread_pct - prev_spread, 8)
        lf_val = _lakhs(la)
        rf_val = _lakhs(lr)
        session.add(PairFeature(
            canonical_pair_id=pair_id,
            expiry_left=None, expiry_right=None,  # no expiry dimension in this corpus
            trade_date=d,
            spread_pct=round(spread_pct, 8),
            spread_change_pct=change,
            price_ratio=round(a / b, 8),
            left_volume_lots=la.derivation_inputs.get("lots") if la.derivation_inputs else None,
            right_volume_lots=lr.derivation_inputs.get("lots") if lr.derivation_inputs else None,
            left_value_lakhs=lf_val,
            right_value_lakhs=rf_val,
            feature_version=FEATURE_VERSION,
            source_status="PROVISIONAL",
        ))
        prev_spread = spread_pct
        added += 1
    session.commit()
    return {
        "pair_id": pair_id,
        "features_added": added,
        "dates_missing_left_leg": missing_left,
        "dates_missing_right_leg": missing_right,
        "alignment_rule": "same trade_date inner join; no forward-fill",
    }


def _lakhs(np_row: NormalizedPrice) -> float | None:
    inputs = np_row.derivation_inputs or {}
    return inputs.get("total_value_lakhs")
