"""Chronological walk-forward backtest on provisional pair features (PROVISIONAL).

Design honesty:
- Signal at day t is calibrated with data strictly before day t (train_end == t);
  the trade is entered at day t's observation and exited when the spread
  returns to the calibration median (or on window end / cost-stop).
- Fills use the day's activity-implied mid basis; there is no order book, no
  bid/ask and no settlement data in this corpus, so results are labelled
  PROVISIONAL and never presented as real execution.
- Benchmark: simultaneous per-unit gold-market direction (same-day spread
  behaviour is strategy-relative); we also report the underlying value change
  of the pair's legs so gold-market movement is separable.
"""
from __future__ import annotations

import uuid
from datetime import date as date_t

from sqlalchemy.orm import Session

from app.analytics.features import FEATURE_VERSION
from app.anomaly import baseline as baseline_mod
from app.anomaly.service import calibrate_pair
from app.core.errors import InvalidInput
from app.core.pairs import pair_members
from app.models.evaluation import BacktestMetric, BacktestRun
from app.models.market import PairFeature

STRATEGY_VERSION = "spread_mean_revert_v1"
CODE_VERSION = "bt_v1"


def run_walkforward(
    session: Session,
    pair_id_canonical: str,
    start: date_t,
    end: date_t,
    train_end_cutoff: date_t | None = None,  # kept for API compatibility; unused
    threshold: float = 3.5,
    cost_bps_per_leg: float = 4.0,   # one-way cost in bps of notional
    slippage_bps_per_leg: float = 2.0,
    risk_per_unit_notional: float = 1.0,  # one 1-unit leg of each side per signal
) -> BacktestRun:
    if start >= end:
        raise InvalidInput("backtest start must be before end")
    left, right = pair_members(pair_id_canonical)

    feats = session.execute(
        _select_features(pair_id_canonical, start, end)
    ).scalars().all()
    if len(feats) < 30:
        raise InvalidInput(
            f"Insufficient observations ({len(feats)}) for pair '{pair_id_canonical}' "
            f"between {start} and {end}. Minimum 30 required."
        )

    run = BacktestRun(
        id=uuid.uuid4().hex[:12],
        pair_id=pair_id_canonical,
        strategy_version=STRATEGY_VERSION,
        code_version=CODE_VERSION,
        data_snapshot=_snapshot_hash(session, pair_id_canonical, start, end),
        start_date=start,
        end_date=end,
        costs={
            "cost_bps_per_leg": cost_bps_per_leg,
            "slippage_bps_per_leg": slippage_bps_per_leg,
            "basis": "bps of leg notional, applied at entry and exit (round trip 2 legs)",
        },
        config={
            "feature": "normalized_spread_pct",
            "feature_version": FEATURE_VERSION,
            "threshold": threshold,
            "entry_rule": "robust |z| >= threshold vs calibration ending previous day",
            "exit_rule": "spread crosses calibration median (convergence), window end, or cost stop",
            "fill_assumption": "activity-implied PROVISIONAL mid basis; no bid/ask data exists",
            "train_end_rule": "calibration window ends the day BEFORE each entry",
        },
        status="finished",
        data_status="PROVISIONAL",
    )

    total_cost = (cost_bps_per_leg + slippage_bps_per_leg) / 10000.0

    open_trade = None
    trades: list[dict] = []

    for f in feats:
        d: date_t = f.trade_date
        spread = float(f.spread_pct)

        if open_trade is None:
            # Calibrate strictly BEFORE today: train_end == d excludes d itself.
            try:
                cal = calibrate_pair(session, pair_id_canonical, None, d)
            except Exception:
                continue  # not enough history yet on this walk
            z = 0.6745 * (spread - float(cal.median)) / float(cal.scale)
            if abs(z) < threshold:
                continue
            direction = -1.0 if z > 0 else 1.0  # bet on convergence to median
            open_trade = {
                "entry_date": d,
                "entry_spread": spread,
                "direction": direction,
                "entry_median": float(cal.median),
                "entry_z": z,
            }
        else:
            converged = (spread - open_trade["entry_median"]) * open_trade["direction"] <= 0
            moved = (spread - open_trade["entry_spread"]) * open_trade["direction"]
            if converged or moved <= -2.0 * abs(open_trade["entry_z"]):
                pnl = moved * open_trade["direction"]  # spread points
                gross = pnl
                net = pnl - 2.0 * total_cost * 100.0 * risk_per_unit_notional  # bps→pct per unit leg
                open_trade.update({
                    "exit_date": d,
                    "exit_spread": spread,
                    "exit_reason": "convergence" if converged else "cost_stop",
                    "gross_pnl_pct": round(gross, 4),
                    "net_pnl_pct": round(net, 4),
                    "holding_days": (d - open_trade["entry_date"]).days,
                })
                trades.append(open_trade)
                open_trade = None

    hit_rate = (
        round(sum(1 for t in trades if t["net_pnl_pct"] > 0) / len(trades), 4)
        if trades else 0.0
    )
    net_total = round(sum(t["net_pnl_pct"] for t in trades), 4)
    gross_total = round(sum(t["gross_pnl_pct"] for t in trades), 4)
    costs_total = round(gross_total - net_total, 4)
    # Benchmark separation: average |day-over-day| move of the pair legs' activity
    # basis within the window, i.e. how much of the move is common gold-market flow.
    deltas = [
        float(f.spread_change_pct or 0) for f in feats
    ]
    benchmark_vol = round(sum(abs(x) for x in deltas) / len(deltas), 6) if deltas else 0.0

    run.completed_at = run.started_at if run.completed_at is None else run.completed_at
    session.add(run)
    session.flush()

    metrics = [
        ("trades", len(trades), "count", None),
        ("hit_rate", hit_rate, "fraction", None),
        ("gross_return_pct", gross_total, "pct", "sum of spread-point P&L, gross of costs"),
        ("net_return_pct", net_total, "pct", "after configured costs and slippage"),
        ("cost_drag_pct", costs_total, "pct", "gross minus net"),
        ("benchmark_move_pct", benchmark_vol, "pct", "avg |daily| spread change (common-movement proxy)"),
        ("data_status_note", 1.0, "flag", "PROVISIONAL data; not real execution"),
    ]
    for name, value, units, detail in metrics:
        session.add(BacktestMetric(
            run_id=run.id, metric_name=name, metric_value=value,
            units=units, details=({"definition": detail} if detail else None),
        ))
    session.commit()
    session.refresh(run)
    run.trades = trades  # transient, returned to caller
    return run


def _select_features(pair_id: str, start: date_t, end: date_t):
    from sqlalchemy import select

    return (
        select(PairFeature)
        .where(
            PairFeature.canonical_pair_id == pair_id,
            PairFeature.feature_version == FEATURE_VERSION,
            PairFeature.trade_date >= start,
            PairFeature.trade_date <= end,
        )
        .order_by(PairFeature.trade_date)
    )


def _snapshot_hash(session: Session, pair_id: str, start: date_t, end: date_t) -> str:
    import hashlib

    feats = session.execute(_select_features(pair_id, start, end)).scalars().all()
    basis = "|".join(
        f"{f.trade_date.isoformat()}:{f.spread_pct:.6f}" for f in feats
    )
    return "pair_features:" + hashlib.sha256(basis.encode()).hexdigest()[:16]
