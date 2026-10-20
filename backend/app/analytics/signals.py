"""Signal evaluation: separates statistical classification from disposition.

Dispositions: ANOMALOUS/NORMAL/UNSCORABLE status plus ACTIONABLE/WATCH/IGNORE
disposition. An observation that is statistically anomalous can still be
IGNORE/UNSCORABLE when expiry, liquidity or data quality make it unassessable.
All checks derive from features that actually exist; missing data yields
UNSCORABLE rather than manufactured confidence.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import AnomalyScore, SignalEvaluation
from app.models.market import PairFeature


def evaluate_signal(session: Session, score: AnomalyScore) -> SignalEvaluation:
    existing = session.execute(
        select(SignalEvaluation).where(SignalEvaluation.score_id == score.id)
    ).scalar_one_or_none()
    if existing:
        return existing

    checks: list[dict] = []
    reasons: list[str] = []

    # 1. Data-quality stage: activity-implied provisional data is scorable but
    #    never verified.
    checks.append({
        "stage": "data_quality",
        "result": "PASS_WITH_CAVEATS",
        "detail": "Activity-implied PROVISIONAL spread; not settlement-price data.",
    })
    reasons.append("activity_implied_provisional_data")

    # 2. Expiry/lifecycle stage: the corpus has no expiry dates at all.
    checks.append({
        "stage": "expiry",
        "result": "UNSCORABLE",
        "detail": "Source corpus contains no expiry dates; days-to-expiry unavailable.",
    })
    reasons.append("expiry_unassessable")
    expiry_status = "UNSCORABLE"

    # 3. Liquidity stage: activity totals are not depth; a volume collapse in
    #    the thinner leg is a warning only.
    feat = session.execute(
        select(PairFeature).where(
            PairFeature.canonical_pair_id == score.pair_id,
            PairFeature.trade_date == score.observation_date,
        )
    ).scalar_one_or_none()
    liquidity_status = "UNSCORABLE"
    if feat and feat.left_volume_lots and feat.right_volume_lots:
        total = (feat.left_volume_lots or 0) + (feat.right_volume_lots or 0)
        if total == 0:
            checks.append({"stage": "liquidity", "result": "FAIL", "detail": "zero activity both legs"})
            reasons.append("zero_activity")
        elif total < 1000:
            liquidity_status = "LOW"
            checks.append({"stage": "liquidity", "result": "WARN", "detail": f"combined lots {total} thin"})
            reasons.append("thin_activity")
        else:
            liquidity_status = "OK"
            checks.append({"stage": "liquidity", "result": "PASS", "detail": f"combined lots {total}"})
    else:
        checks.append({
            "stage": "liquidity",
            "result": "UNSCORABLE",
            "detail": "leg-level lots unavailable for this observation",
        })
        reasons.append("liquidity_missing")

    # 4. Cost stage: configurable assumptions exist but no execution-quality
    #    data; costs cannot be verified against real fills.
    checks.append({
        "stage": "costs",
        "result": "PASS_WITH_ASSUMPTIONS",
        "detail": "Cost model is config-driven; no bid/ask or execution data exists.",
    })
    reasons.append("costs_assumption_only")
    cost_status = "ASSUMPTION"

    # 5. Historical convergence: not used to label current signals; outcome
    #    assessment happens only inside backtests with explicit windows.
    checks.append({
        "stage": "convergence",
        "result": "NOT_EVALUATED",
        "detail": "Convergence assessed only in backtests, never as live guarantee.",
    })

    # Disposition decision (anomaly label preserved separately).
    if score.is_anomaly:
        status = "ANOMALOUS"
        if expiry_status == "UNSCORABLE":
            disposition = "WATCH"
            reasons.append("anomaly_but_expiry_unassessable")
        elif liquidity_status in ("LOW",):
            disposition = "WATCH"
            reasons.append("liquidity_warning")
        else:
            disposition = "WATCH"
            reasons.append("no_verified_execution_data")
    else:
        status = "NORMAL"
        disposition = "IGNORE"
        reasons.append("inside_learned_normal_region")

    row = SignalEvaluation(
        score_id=score.id,
        status=status,
        disposition=disposition,
        liquidity_status=liquidity_status,
        expiry_status=expiry_status,
        cost_status=cost_status,
        checks=checks,
        reason_codes=reasons,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
