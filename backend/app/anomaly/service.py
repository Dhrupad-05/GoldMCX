"""Calibration and scoring service with temporal isolation + explainability.

Rules enforced:
- Calibration uses only observations strictly BEFORE the cutoff (the scored
  observation itself can never enter its own calibration sample).
- Pair-specific calibrations; no cross-pair pooling without tested justification.
- Deterministic outputs; every result carries algorithm + feature versions.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics.features import FEATURE_VERSION
from app.anomaly.baseline import (
    ALGORITHM_VERSION,
    CalibrationStats,
    THRESHOLD,
    anomaly_score,
    compute_training_stats,
    severity_for,
)
from app.core.errors import InvalidInput, NotFound
from app.core.pairs import pair_members
from app.models.evaluation import AnomalyScore, ModelCalibration
from app.models.market import PairFeature

FEATURE_NAME = "normalized_spread_pct"


def _spread_series(session: Session, pair_id: str) -> list[tuple[date, float]]:
    rows = session.execute(
        select(PairFeature).where(
            PairFeature.canonical_pair_id == pair_id,
            PairFeature.feature_version == FEATURE_VERSION,
        ).order_by(PairFeature.trade_date)
    ).scalars().all()
    return [(r.trade_date, float(r.spread_pct)) for r in rows]


def calibrate_pair(
    session: Session,
    pair_id: str,
    train_start: date | None,
    train_end: date | None,
    cutoff: datetime | None = None,
    threshold: float = THRESHOLD,
    scale_floor_fraction: float | None = None,
) -> ModelCalibration:
    """Create a calibration version. Scores AFTER train_end only; excludes cutoff."""
    left, right = pair_members(pair_id)  # validates pair id and symbols
    cutoff = cutoff or datetime.now(timezone.utc).replace(tzinfo=None)
    if not (1.0 <= threshold <= 99.0):
        raise InvalidInput("threshold must be within [1, 99].")
    if scale_floor_fraction is not None and not (0.0 < scale_floor_fraction <= 1.0):
        raise InvalidInput("scale_floor_fraction must be within (0, 1].")
    series = _spread_series(session, pair_id)
    if not series:
        raise InvalidInput(f"Pair '{pair_id}' has no computed pair features to calibrate on.")

    end = train_end or max(d for d, _ in series)
    start = train_start or min(d for d, _ in series)
    if start > end:
        raise InvalidInput("train_start after train_end.")
    # Temporal isolation: exclude the train_end boundary day itself from the
    # training sample (day-of decision uses only prior information).
    training = [(d, v) for d, v in series if start <= d < end]
    if len(training) < 10:
        raise InvalidInput(
            f"Insufficient training observations ({len(training)}) before {end} for pair '{pair_id}'."
        )
    values = [v for _, v in training]

    kwargs: dict = {}
    if scale_floor_fraction is not None:
        kwargs["scale_floor_fraction"] = scale_floor_fraction
    stats: CalibrationStats = compute_training_stats(values, threshold=threshold, **kwargs)

    existing = session.execute(
        select(ModelCalibration).where(
            ModelCalibration.pair_id == pair_id,
            ModelCalibration.algorithm_version == ALGORITHM_VERSION,
            ModelCalibration.train_start == start,
            ModelCalibration.train_end == end,
            ModelCalibration.cutoff_ts == cutoff,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    cal = ModelCalibration(
        pair_id=pair_id,
        algorithm_version=ALGORITHM_VERSION,
        feature_version=FEATURE_VERSION,
        train_start=start,
        train_end=end,
        cutoff_ts=cutoff,
        n=stats.n,
        median=stats.median,
        scale=stats.scale,
        scale_method=stats.scale_method,
        threshold=threshold,
        training_row_ids=[d.isoformat() for d, _ in training],
        config={
            "feature": FEATURE_NAME,
            "excluded_boundary": end.isoformat(),
            "z_factor": 0.6745,
            "score_denominator": 6,
        },
        data_status_note="trained on activity-implied PROVISIONAL spreads",
    )
    session.add(cal)
    session.commit()
    session.refresh(cal)
    return cal


def default_calibration(session: Session, pair_id: str):
    cal = session.execute(
        select(ModelCalibration)
        .where(ModelCalibration.pair_id == pair_id)
        .order_by(ModelCalibration.created_at.desc())
        .limit(1)
    ).scalars().first()
    if cal is None:
        # Auto-calibrate on history strictly ending before the last feature date
        # (yesterday as train_end); the last day stays held out.
        series = _spread_series(session, pair_id)
        if not series:
            raise InvalidInput(f"Pair '{pair_id}' has no pair features to calibrate on.")
        return calibrate_pair(session, pair_id, None, max(d for d, _ in series))
    return cal


def score_observation(
    session: Session,
    pair_id: str,
    observation_date: date,
    cal: ModelCalibration,
    value: float | None = None,
) -> AnomalyScore:
    """Score one observation without ever using it (or later data) in calibration."""
    stats = CalibrationStats(
        n=cal.n, median=float(cal.median), scale=float(cal.scale),
        scale_method=cal.scale_method, threshold=float(cal.threshold),
    )

    if value is None:
        feat = session.execute(
            select(PairFeature).where(
                PairFeature.canonical_pair_id == pair_id,
                PairFeature.trade_date == observation_date,
                PairFeature.feature_version == FEATURE_VERSION,
            )
        ).scalar_one_or_none()
        if feat is None:
            raise NotFound(
                f"No pair feature for '{pair_id}' on {observation_date}. "
                "Provide 'value' explicitly or compute features first."
            )
        value = float(feat.spread_pct)
        feature_values = {
            "spread_pct": value,
            "spread_change_pct": float(feat.spread_change_pct) if feat.spread_change_pct is not None else None,
            "price_ratio": float(feat.price_ratio) if feat.price_ratio is not None else None,
            "left_value_lakhs": float(feat.left_value_lakhs) if feat.left_value_lakhs is not None else None,
            "right_value_lakhs": float(feat.right_value_lakhs) if feat.right_value_lakhs is not None else None,
            "left_volume_lots": feat.left_volume_lots,
            "right_volume_lots": feat.right_volume_lots,
        }
    else:
        feature_values = {FEATURE_NAME: value}

    if observation_date.isoformat() in (cal.training_row_ids or []):
        # Defensive: training_row_ids are stored as ISO strings (JSON); never
        # silently score an observation that participated in its own calibration.
        raise InvalidInput("Scoring would violate calibration isolation.")

    z, score, is_anomaly = anomaly_score(value, stats)
    az = abs(z)
    explanation = _explain(value, stats, az, is_anomaly)

    existing = session.execute(
        select(AnomalyScore).where(
            AnomalyScore.calibration_id == cal.id,
            AnomalyScore.pair_id == pair_id,
            AnomalyScore.observation_date == observation_date,
            AnomalyScore.feature == FEATURE_NAME,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    row = AnomalyScore(
        calibration_id=cal.id,
        pair_id=pair_id,
        observation_date=observation_date,
        feature=FEATURE_NAME,
        observed_value=value,
        robust_z=z,
        score=score,
        is_anomaly=is_anomaly,
        severity=severity_for(az, float(cal.threshold)),
        explanation=explanation,
        warnings=_warnings(cal),
        feature_values=feature_values,
        data_status="PROVISIONAL",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _calibration_dict(cal: ModelCalibration) -> dict:
    return {
        "id": cal.id,
        "pair_id": cal.pair_id,
        "algorithm_version": cal.algorithm_version,
        "feature_version": cal.feature_version,
        "train_start": cal.train_start,
        "train_end": cal.train_end,
        "cutoff_ts": cal.cutoff_ts,
        "n": cal.n,
        "median": float(cal.median),
        "scale": float(cal.scale),
        "scale_method": cal.scale_method,
        "threshold": float(cal.threshold),
        "data_status_note": cal.data_status_note,
    }


def _explain(value: float, stats: CalibrationStats, az: float, is_anomaly: bool) -> str:
    if is_anomaly:
        return (
            f"Unusual relative spread: the observation lies {az:.1f} robust sigma "
            f"outside the normal spread range learned from {stats.n} mostly-normal "
            f"training observations (scale via {stats.scale_method.upper()})."
        )
    return (
        f"Within the normal region: the observation sits {az:.1f} robust sigma from "
        f"the training centre of {stats.n} observations (scale via {stats.scale_method.upper()})."
    )


def _warnings(cal: ModelCalibration) -> list[str]:
    w = [
        "Activity-implied data: scores derive from value-per-lot aggregates, not settlement prices.",
        "Expiry-window features unavailable: the corpus has no expiry dates (expiry checks UNSCORABLE).",
        "No volume/OI depth data: activity totals are not market depth.",
    ]
    if cal.scale_method == "floor":
        w.append("Degenerate training spread (MAD and IQR both ~0): configured scale floor applied.")
    elif cal.scale_method == "iqr":
        w.append("MAD was ~0: IQR/1.349 fallback scale used.")
    return w


def score_detail_dict(session: Session, row: AnomalyScore) -> dict:
    cal = session.get(ModelCalibration, row.calibration_id)
    return {
        "id": row.id,
        "pair_id": row.pair_id,
        "observation_date": row.observation_date,
        "data_status": row.data_status,
        "algorithm": cal.algorithm_version if cal else ALGORITHM_VERSION,
        "algorithm_version": cal.algorithm_version if cal else ALGORITHM_VERSION,
        "feature": row.feature,
        "feature_version": cal.feature_version if cal else FEATURE_VERSION,
        "calibration": _calibration_dict(cal) if cal else {},
        "observed_value": float(row.observed_value),
        "training_median": float(cal.median) if cal else None,
        "scale_value": float(cal.scale) if cal else None,
        "scale_method": cal.scale_method if cal else None,
        "robust_z": float(row.robust_z),
        "anomaly_score": float(row.score),
        "is_anomaly": bool(row.is_anomaly),
        "severity": row.severity,
        "explanation": row.explanation,
        "warnings": row.warnings or [],
        "feature_values": row.feature_values or {},
        "threshold": float(cal.threshold) if cal else THRESHOLD,
        "provenance": {
            "training_dates": (cal.training_row_ids or [])[:5] + (["..."] if cal and cal.training_row_ids and len(cal.training_row_ids) > 5 else []),
            "data_root_note": "derived from GoldMcx_Data activity reports",
        },
    }
