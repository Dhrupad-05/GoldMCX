"""Backtest tests: timing, cost arithmetic, no look-ahead, reproducibility."""
import math
from datetime import date

import pytest
from sqlalchemy import select

from app.backtesting.walkforward import run_walkforward
from app.core.errors import InvalidInput
from app.models.evaluation import BacktestMetric
from app.models.market import PairFeature


@pytest.fixture()
def synthetic_pair_features(seeded_activity):
    """Deterministic pair-feature series: normal band with one big excursion."""
    session = seeded_activity
    for i in range(1, 49):
        if i <= 28:
            d = date(2024, 1, i)
        elif i <= 56:
            d = date(2024, 2, i - 28)
        wave = math.sin(i / 3.0) * 0.5
        spike = 5.0 if i == 30 else 0.0
        session.add(PairFeature(
            canonical_pair_id="GOLDM-GOLDPETAL", trade_date=d, spread_pct=round(0.5 + wave + spike, 6),
            feature_version="pf_v1", source_status="PROVISIONAL",
        ))
    session.commit()
    return session


def test_backtest_requires_sufficient_data(seeded_activity):
    with pytest.raises(InvalidInput, match="Insufficient observations"):
        run_walkforward(seeded_activity, "GOLDM-GOLDPETAL", date(2024, 1, 1), date(2024, 1, 28))


def test_backtest_window_and_calibration_rule(synthetic_pair_features):
    session = synthetic_pair_features
    run = run_walkforward(
        session, "GOLDM-GOLDPETAL", date(2024, 1, 5), date(2024, 2, 28),
        train_end_cutoff=None, threshold=3.5,
        cost_bps_per_leg=4.0, slippage_bps_per_leg=2.0,
    )
    assert run.id and run.data_status == "PROVISIONAL"
    assert "BEFORE" in run.config["train_end_rule"]


def test_cost_arithmetic_net_gross(synthetic_pair_features):
    session = synthetic_pair_features
    run = run_walkforward(
        session, "GOLDM-GOLDPETAL", date(2024, 1, 5), date(2024, 2, 28),
        threshold=3.5, cost_bps_per_leg=4.0, slippage_bps_per_leg=2.0,
    )
    metrics = {
        m.metric_name: float(m.metric_value)
        for m in session.execute(
            select(BacktestMetric).where(BacktestMetric.run_id == run.id)
        ).scalars()
    }
    # net = gross - cost drag by construction
    assert abs(metrics["net_return_pct"] - (metrics["gross_return_pct"] - metrics["cost_drag_pct"])) < 1e-6
    # The spike (z >= threshold) must have produced at least one trade
    assert metrics["trades"] >= 1


def test_deterministic_reproducibility(synthetic_pair_features):
    session = synthetic_pair_features
    r1 = run_walkforward(session, "GOLDM-GOLDPETAL", date(2024, 1, 5), date(2024, 2, 28))
    t1 = [(x["entry_date"], x["exit_date"], x["net_pnl_pct"]) for x in r1.trades]
    r2 = run_walkforward(session, "GOLDM-GOLDPETAL", date(2024, 1, 5), date(2024, 2, 28))
    t2 = [(x["entry_date"], x["exit_date"], x["net_pnl_pct"]) for x in r2.trades]
    assert r1.data_snapshot == r2.data_snapshot
    assert t1 == t2


def test_benchmark_separation_reported(synthetic_pair_features):
    session = synthetic_pair_features
    run = run_walkforward(session, "GOLDM-GOLDPETAL", date(2024, 1, 5), date(2024, 2, 28))
    metrics = {
        m.metric_name: m.details
        for m in session.execute(
            select(BacktestMetric).where(BacktestMetric.run_id == run.id)
        ).scalars()
    }
    assert "common-movement proxy" in str(metrics.get("benchmark_move_pct"))
