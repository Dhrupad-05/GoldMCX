"""Contracts endpoints."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.core.pairs import require_symbol
from app.db.session import get_session
from app.models.market import NormalizedPrice
from app.schemas.api import ContractOut, SeriesResponse, NormalizedPricePoint
from app.services.market_builder import contract_inventory

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
def list_contracts(session: Session = Depends(get_session)):
    return {"contracts": contract_inventory(session)}


@router.get("/{symbol}")
def get_contract(symbol: str, session: Session = Depends(get_session)):
    require_symbol(symbol)
    inv = contract_inventory(session)
    found = next((c for c in inv if c["symbol"] == symbol), None)
    if found is None or not found.get("data_summary", {}).get("detail_days", 0):
        raise NotFound(f"No activity data registered for symbol '{symbol}'.")
    return ContractOut(
        symbol=symbol,
        display_name=found["display_name"],
        specs=found["specs"],
        data_summary=found["data_summary"],
    )


@router.get("/{symbol}/series", response_model=SeriesResponse)
def get_series(
    symbol: str,
    start: date | None = Query(default=None, alias="start"),
    end: date | None = Query(default=None, alias="end"),
    session: Session = Depends(get_session),
):
    require_symbol(symbol)
    q = (
        select(NormalizedPrice)
        .where(
            NormalizedPrice.symbol == symbol,
            NormalizedPrice.derivation_method == "activity_implied_value_per_lot",
        )
        .order_by(NormalizedPrice.trade_date)
    )
    if start:
        q = q.where(NormalizedPrice.trade_date >= start)
    if end:
        q = q.where(NormalizedPrice.trade_date <= end)
    rows = session.execute(q).scalars().all()
    if not rows:
        # An empty verified-history dataset is an explicit 200 NO_DATA response,
        # not a failure: the frontend renders the no-data state without a 404.
        return SeriesResponse(
            symbol=symbol,
            derivation_method="none",
            data_status="NO_DATA",
            points=[],
            spec_versions_applied=[],
        )
    return SeriesResponse(
        symbol=symbol,
        derivation_method="activity_implied_value_per_lot",
        data_status="PROVISIONAL",
        points=[
            NormalizedPricePoint(
                trade_date=r.trade_date,
                normalized_value=float(r.normalized_value),
                source_status=r.source_status,
                derivation_method=r.derivation_method,
            )
            for r in rows
        ],
        spec_versions_applied=sorted({str(r.spec_version_id) for r in rows}),
    )
