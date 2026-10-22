"""Backtest endpoints. Runs are synchronous (small local data) and stored."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting import walkforward
from app.core.errors import NotFound
from app.core.idempotency import (
    commit_result,
    idempotency_key_of,
    replay_or_claim,
    request_fingerprint,
)
from app.core.pairs import resolve_pair_id
from app.db.session import get_session
from app.models.evaluation import BacktestMetric, BacktestRun

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestRequest(BaseModel):
    pair_id: str
    start: date
    end: date
    threshold: float = Field(default=3.5, ge=1, le=99)
    cost_bps_per_leg: float = Field(default=4.0, ge=0, le=100)
    slippage_bps_per_leg: float = Field(default=2.0, ge=0, le=100)


@router.get("")
def list_backtests(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.execute(
        select(BacktestRun).order_by(BacktestRun.started_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "pair_id": r.pair_id,
            "strategy_version": r.strategy_version,
            "code_version": r.code_version,
            "data_status": r.data_status,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "costs": r.costs,
            "config": r.config,
            "status": r.status,
            "started_at": r.started_at,
        }
        for r in rows
    ]


def run_walkforward_guarded(session: Session, canonical: str, body: BacktestRequest,
                            **overrides) -> "BacktestRun":
    """Run the walk-forward inside the documented ordered advisory locks.

    Resources (in global order): pair:<canonical> and backtest:<run-scope>;
    locks release with the transaction (strict two-phase)."""
    from app.db.locking import locked

    with locked(session, f"pair:{canonical}", f"backtest:{body.start}-{body.end}-{body.pair_id}"):
        return walkforward.run_walkforward(
            session,
            canonical,
            body.start,
            body.end,
            train_end_cutoff=None,
            threshold=overrides.get("threshold", body.threshold),
            cost_bps_per_leg=overrides.get("cost_bps_per_leg", body.cost_bps_per_leg),
            slippage_bps_per_leg=overrides.get("slippage_bps_per_leg", body.slippage_bps_per_leg),
        )


@router.post("/run")
def run_backtest(request: Request, body: BacktestRequest, session: Session = Depends(get_session)):
    canonical = resolve_pair_id(body.pair_id)
    route = "POST /api/v1/backtests/run"
    idem_key = idempotency_key_of(request)
    body_hash = request_fingerprint(body.model_dump(mode="json"))
    if idem_key:
        replay = replay_or_claim(session, route, idem_key, body_hash)
        if replay["payload"] is not None:
            return replay["payload"]
    run = run_walkforward_guarded(
        session, canonical, body, threshold=body.threshold,
        cost_bps_per_leg=body.cost_bps_per_leg,
        slippage_bps_per_leg=body.slippage_bps_per_leg,
    )
    metrics = session.execute(
        select(BacktestMetric).where(BacktestMetric.run_id == run.id)
    ).scalars().all()
    response = {
        "run": {
            "id": run.id,
            "pair_id": canonical,
            "strategy_version": run.strategy_version,
            "code_version": run.code_version,
            "data_status": run.data_status,
            "data_snapshot": run.data_snapshot,
            "start_date": run.start_date,
            "end_date": run.end_date,
            "costs": run.costs,
            "config": run.config,
            "status": run.status,
        },
        "metrics": [
            {
                "metric_name": m.metric_name,
                "metric_value": float(m.metric_value),
                "units": m.units,
                "details": m.details,
            }
            for m in metrics
        ],
        "trades": getattr(run, "trades", []),
        "disclaimer": (
            "PROVISIONAL activity-implied data; no bid/ask, settlement or depth data exists. "
            "Results are strategy-relative screening evidence, not proven profitability."
        ),
    }
    if idem_key:
        commit_result(session, route, idem_key, body_hash, response, result_ref=run.id)
        session.commit()
    return response
