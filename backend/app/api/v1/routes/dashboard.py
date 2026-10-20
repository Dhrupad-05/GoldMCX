"""Dashboard summary endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.evaluation import AnomalyScore, SignalEvaluation
from app.schemas.api import DashboardSummary, SignalOut
from app.services.market_builder import contract_inventory, data_freshness

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard(
    limit: int = Query(default=8, le=25),
    session: Session = Depends(get_session),
):
    contracts = contract_inventory(session)
    out = DashboardSummary(
        contracts=contracts,
        data_status="PROVISIONAL",
        data_freshness=data_freshness(session),
        source_quality={
            "nivel": "activity_reports_only",
            "note": (
                "The supplied corpus contains activity reports and contract-spec PDFs "
                "only; no OHLC/settlement/expiry data exists. All derived market values "
                "are activity-implied and PROVISIONAL."
            ),
        },
        top_signals=[],
    )
    rows = session.execute(
        select(SignalEvaluation, AnomalyScore)
        .where(SignalEvaluation.status == "ANOMALOUS")
        .join(AnomalyScore, SignalEvaluation.score_id == AnomalyScore.id)
        .order_by(AnomalyScore.observation_date.desc())
        .limit(limit)
    ).all()
    for sig, score in rows:
        out.top_signals.append(SignalOut(
            id=sig.id,
            score_id=score.id,
            pair_id=score.pair_id,
            observation_date=score.observation_date,
            status=sig.status,
            disposition=sig.disposition,
            severity=score.severity,
            robust_z=float(score.robust_z),
            score=float(score.score),
            liquidity_status=sig.liquidity_status,
            expiry_status=sig.expiry_status,
            cost_status=sig.cost_status,
            reason_codes=sig.reason_codes or [],
            data_status=score.data_status,
        ))
    return out
