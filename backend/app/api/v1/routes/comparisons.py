"""Comparison endpoints: normalized pair series/features."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.features import FEATURE_VERSION
from app.core.errors import InvalidInput, NotFound
from app.core.pairs import canonical_pair_id, pair_members, resolve_pair_id
from app.db.session import get_session
from app.models.market import PairFeature
from app.schemas.api import ComparisonPoint, ComparisonResponse

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

    q = select(PairFeature).where(
        PairFeature.canonical_pair_id == canonical,
        PairFeature.feature_version == FEATURE_VERSION,
    ).order_by(PairFeature.trade_date)
    rows = session.execute(q).scalars().all()
    if not rows:
        raise NotFound(f"No pair features computed for '{canonical}'.")
    if range_days:
        end_date = rows[-1].trade_date
        from datetime import timedelta
        q_start = end_date - timedelta(days=range_days)
        rows = [x for x in rows if x.trade_date >= q_start]
    if start:
        rows = [x for x in rows if x.trade_date >= start]
    if end:
        rows = [x for x in rows if x.trade_date <= end]
    if not rows:
        raise NotFound("No observations in the requested range for '{}'.".format(canonical))

    return ComparisonResponse(
        pair_id=canonical,
        left=l,
        right=r,
        range_start=rows[0].trade_date,
        range_end=rows[-1].trade_date,
        derivation_method="activity_implied_value_per_lot",
        data_status="PROVISIONAL",
        point_count=len(rows),
        points=[
            ComparisonPoint(
                trade_date=x.trade_date,
                spread_pct=float(x.spread_pct),
                spread_change_pct=float(x.spread_change_pct) if x.spread_change_pct is not None else None,
                price_ratio=float(x.price_ratio) if x.price_ratio is not None else None,
                left_value_lakhs=float(x.left_value_lakhs) if x.left_value_lakhs is not None else None,
                right_value_lakhs=float(x.right_value_lakhs) if x.right_value_lakhs is not None else None,
                source_status=x.source_status,
            )
            for x in rows
        ],
    )
