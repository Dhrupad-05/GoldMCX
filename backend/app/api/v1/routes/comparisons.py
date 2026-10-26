"""Comparison endpoints: normalized pair series/features."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.features import FEATURE_VERSION
from app.cache import TTL_DEFAULTS, get_cache
from app.core.errors import InvalidInput, NotFound
from app.core.pairs import canonical_pair_id, pair_members, resolve_pair_id
from app.db.session import get_session
from app.models.market import PairFeature
from app.schemas.api import ComparisonResponse

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.get("", response_model=ComparisonResponse)
def compare(
    left: str | None = None,
    right: str | None = None,
    pair: str | None = None,
    start: date | None = None,
    end: date | None = None,
    range_days: int | None = None,
    session: Session = Depends(get_session),
):
    """Accept either ?left=&right= symbols or ?pair=<pair id or legacy alias>."""
    if pair:
        canonical = resolve_pair_id(pair)
    elif not left or not right:
        raise InvalidInput("Provide both 'left' and 'right' symbols, or a 'pair' id.")
    else:
        canonical = canonical_pair_id(left, right)
    l, r = pair_members(canonical)
    _ = (l, r)  # orientation irrelevant: canonical orientation is authoritative

    # All range filtering happens in SQL (bounded result sets; no full scan).
    # The read path goes through the cache facade; the dataset epoch in the key
    # is bumped after successful data commits, so refreshed data is served.
    cache = get_cache()
    params = {
        "pair": canonical,
        "feature_version": FEATURE_VERSION,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "range_days": range_days,
    }

    def _load() -> dict:
        conds = [
            PairFeature.canonical_pair_id == canonical,
            PairFeature.feature_version == FEATURE_VERSION,
        ]
        if start:
            conds.append(PairFeature.trade_date >= start)
        if end:
            conds.append(PairFeature.trade_date <= end)
        if range_days:
            from datetime import timedelta

            floor = date.today() - timedelta(days=range_days)
            conds.append(PairFeature.trade_date >= floor)
        q = (
            select(PairFeature)
            .where(*conds)
            .order_by(PairFeature.trade_date)
        )
        rows = session.execute(q).scalars().all()
        if not rows:
            raise NotFound(f"No pair features computed for '{canonical}' in the requested range.")
        return {
            "pair_id": canonical,
            "left": l,
            "right": r,
            "range_start": rows[0].trade_date.isoformat(),
            "range_end": rows[-1].trade_date.isoformat(),
            "derivation_method": "activity_implied_value_per_lot",
            "data_status": "PROVISIONAL",
            "point_count": len(rows),
            "points": [
                {
                    "trade_date": x.trade_date.isoformat(),
                    "spread_pct": float(x.spread_pct),
                    "spread_change_pct": float(x.spread_change_pct) if x.spread_change_pct is not None else None,
                    "price_ratio": float(x.price_ratio) if x.price_ratio is not None else None,
                    "left_value_lakhs": float(x.left_value_lakhs) if x.left_value_lakhs is not None else None,
                    "right_value_lakhs": float(x.right_value_lakhs) if x.right_value_lakhs is not None else None,
                    "source_status": x.source_status,
                }
                for x in rows
            ],
        }

    cached = cache.get_or_load(
        cache.key("comparisons", params), TTL_DEFAULTS.comparisons, _load
    )
    return ComparisonResponse(**cached)
