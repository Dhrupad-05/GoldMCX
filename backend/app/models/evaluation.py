"""Analytics and evaluation models: calibrations, scores, signals, backtests."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelCalibration(Base):
    """Reproducible calibration metadata for one pair, window and algorithm version."""
    __tablename__ = "model_calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="robust_mad_v1")
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="pf_v1")
    train_start: Mapped[date] = mapped_column(Date, nullable=False)
    train_end: Mapped[date] = mapped_column(Date, nullable=False)
    cutoff_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    median: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)
    scale: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)
    scale_method: Mapped[str] = mapped_column(String(8), nullable=False)  # mad|iqr|floor
    threshold: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=3.5)
    training_row_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_status_note: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "pair_id", "algorithm_version", "train_start", "train_end", "cutoff_ts",
            name="uq_calibrations_natural",
        ),
    )


class AnomalyScore(Base):
    """Stored scored observation with full explainability payload."""
    __tablename__ = "anomaly_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calibration_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pair_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(48), nullable=False, default="normalized_spread_pct")
    observed_value: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)
    robust_z: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(12, 8), nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Integer, nullable=False)  # 0/1
    severity: Mapped[str] = mapped_column(String(12), nullable=False)  # Normal|Watch|High
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    feature_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PROVISIONAL")
    pair_feature_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Trained-ML provenance: registry model_version when scored by the ML
    # artifact, else None (statistical-robust-MAD calibration rows).
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SignalEvaluation(Base):
    """Separates anomaly detection (AnomalyScore) from post-detection disposition."""
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # ANOMALOUS | NORMAL | UNSCORABLE
    disposition: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # ACTIONABLE | WATCH | IGNORE | UNSCORABLE
    liquidity_status: Mapped[str] = mapped_column(String(16), nullable=False)
    expiry_status: Mapped[str] = mapped_column(String(16), nullable=False)
    cost_status: Mapped[str] = mapped_column(String(16), nullable=False)
    checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reason_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("score_id", name="uq_signals_score"),
    )


class BacktestRun(Base):
    """Reproducible walk-forward run metadata; provisional-data runs are labelled."""
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    pair_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="spread_mean_revert_v1")
    code_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    data_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    costs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="finished")
    data_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PROVISIONAL")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BacktestMetric(Base):
    __tablename__ = "backtest_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    units: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
