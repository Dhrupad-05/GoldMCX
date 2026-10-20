"""Robust novelty baseline (robust_mad_v1).

Parity with the existing frontend baseline (src/lib/anomalyScore.ts):
median, MAD, IQR/1.349 fallback when MAD~0, documented scale floor,
z = 0.6745*(x-median)/scale, score = min(|z|/6, 1), threshold 3.5.

This is a screening heuristic — NOT a probability, NOT evidence of mispricing.
"""
from __future__ import annotations

import statistics
from typing import NamedTuple

ALGORITHM_VERSION = "robust_mad_v1"
THRESHOLD = 3.5
EPSILON = 1e-9
Z_FACTOR = 0.6745
SCORE_DENOM = 6.0
DEFAULT_SCALE_FLOOR_PCT = 0.01  # fraction of |median| ; plus absolute minimum
ABS_MIN_SCALE = 1e-4


class CalibrationStats(NamedTuple):
    n: int
    median: float
    scale: float
    scale_method: str  # mad | iqr | floor
    threshold: float

    def as_dict(self) -> dict:
        return {
            "n": self.n, "median": self.median, "scale": self.scale,
            "scale_method": self.scale_method, "threshold": self.threshold,
        }


def compute_training_stats(
    training_spreads: list[float],
    threshold: float = THRESHOLD,
    scale_floor_fraction: float = DEFAULT_SCALE_FLOOR_PCT,
    abs_min_scale: float = ABS_MIN_SCALE,
) -> CalibrationStats:
    if not training_spreads:
        raise ValueError("empty training sample")
    n = len(training_spreads)
    med = statistics.median(training_spreads)
    mad = statistics.median(abs(x - med) for x in training_spreads)
    if mad > EPSILON:
        return CalibrationStats(n, med, mad, "mad", threshold)

    # IQR/1.349 fallback (same quantile split as the frontend baseline)
    xs = sorted(training_spreads)
    q1 = statistics.median(xs[: n // 2])
    q3 = statistics.median(xs[(n + 1) // 2 :])
    iqr_scale = (q3 - q1) / 1.349
    if iqr_scale > EPSILON:
        return CalibrationStats(n, med, iqr_scale, "iqr", threshold)

    floor = max(abs(med) * scale_floor_fraction, abs_min_scale)
    return CalibrationStats(n, med, floor, "floor", threshold)


def robust_z(x: float, stats: CalibrationStats) -> float:
    return Z_FACTOR * (x - stats.median) / stats.scale if stats.scale > 0 else 0.0


def anomaly_score(x: float, stats: CalibrationStats) -> tuple[float, float, bool]:
    """Return (robust_z, score, is_anomaly) deterministically."""
    z = robust_z(x, stats)
    az = abs(z)
    score = min(az / SCORE_DENOM, 1.0)
    return z, round(score, 8), az >= stats.threshold


def severity_for(az: float, threshold: float) -> str:
    if az >= threshold:
        return "High" if az >= threshold + 1.0 else "Watch"
    return "Normal"
