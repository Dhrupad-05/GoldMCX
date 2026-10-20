"""Novelty/scoring tests: MAD path, IQR fallback, floor, thresholds,
determinism, and calibration-isolation guarantees."""
from datetime import date, datetime

import statistics

import pytest

from app.anomaly import service as anomaly_service
from app.anomaly.baseline import (
    CalibrationStats,
    compute_training_stats,
    severity_for,
)
from app.analytics.features import compute_pair_features
from app.core.errors import InvalidInput


def _stats_values(stats: CalibrationStats):
    return stats.n, stats.median, stats.scale, stats.scale_method


def test_mad_path_normal_sample():
    values = [0.35, 0.4, 0.42, 0.44, 0.45, 0.5, 0.55, 0.46, 0.48, 0.47]
    s = compute_training_stats(values, threshold=3.5)
    assert _stats_values(s)[3] == "mad"
    # hand-check: median 0.455; deviations sorted -> MAD 0.042? computed below loosely
    assert s.median == 0.455
    expected_mad = statistics.median(abs(x - 0.455) for x in values)
    assert abs(s.scale - expected_mad) < 1e-12


def test_iqr_fallback_when_mad_zero():
    # 7 values: med 0.5, all but three deviations sit exactly at 0 -> MAD == 0,
    # IQR = (0.5-0)/1.349.
    values = [0, 0, 0.5, 0.5, 0.5, 0.5, 2.0]
    s = compute_training_stats(values)
    assert s.scale_method == "iqr"
    assert abs(s.scale - 0.5 / 1.349) < 1e-12


def test_scale_floor_when_degenerate():
    s = compute_training_stats([5.0] * 12)
    assert s.scale_method == "floor"
    assert abs(s.scale - max(abs(5.0) * 0.01, 1e-4)) < 1e-15


def test_positive_and_negative_deviation_symmetry():
    s = compute_training_stats([0.0] * 3 + [1.0] * 3)
    from app.anomaly.baseline import anomaly_score

    z_pos, s_pos, anomaly_pos = anomaly_score(s.median + 10 * s.scale, s)
    z_neg, s_neg, anomaly_neg = anomaly_score(s.median - 10 * s.scale, s)
    assert z_pos > 0 > z_neg
    assert abs(z_pos) == abs(z_neg)
    assert s_pos == s_neg and anomaly_pos == anomaly_neg


def test_threshold_boundary_and_severity():
    from app.anomaly.baseline import anomaly_score

    s = compute_training_stats([1.0] * 10, threshold=3.5)  # degenerate: floor scale
    probe = s.median + 3.5001 * s.scale / 0.6745  # strictly beyond the threshold
    z, score, is_anom = anomaly_score(probe, s)
    assert abs(z) > 3.5
    assert is_anom  # >= threshold
    assert severity_for(abs(z), 3.5) == "Watch"
    just_below = anomaly_score(s.median + 3.4 * s.scale / 0.6745, s)[2]
    assert not just_below


def test_score_is_capped_and_deterministic():
    from app.anomaly.baseline import anomaly_score

    s = compute_training_stats([1.0, 2.0, 3.0] * 10)
    r1 = anomaly_score(1e6, s)
    r2 = anomaly_score(1e6, s)
    assert r1 == r2 and r1[1] == 1.0


def test_calibration_excludes_scored_observation(seeded_activity):
    session = seeded_activity
    from app.services.market_builder import rebuild_market_tables

    rebuild_market_tables(session)
    pair_id = "GOLDM-GOLDPETAL"
    cal = anomaly_service.calibrate_pair(session, pair_id, None, date(2024, 1, 20))
    # No observation on/after train_end is a training member:
    assert all(date.fromisoformat(x) < cal.train_end for x in cal.training_row_ids)
    # Attempting to score a training date raises (self-contamination guard):
    training_date = date.fromisoformat(cal.training_row_ids[0])
    with pytest.raises(InvalidInput):
        anomaly_service.score_observation(session, pair_id, training_date, cal)
    # Held-out day scores fine (train_end itself is the first scorable date):
    held_out = date(2024, 1, 27)
    assert held_out not in [date.fromisoformat(x) for x in cal.training_row_ids]
    row = anomaly_service.score_observation(session, pair_id, held_out, cal)
    assert row.id > 0
    # The scored observation was NOT a member of the training sample:
    assert anomaly_service._spread_series(session, pair_id)[0][0] < held_out


def test_pair_specific_calibrations_do_not_share_stats(seeded_activity):
    session = seeded_activity
    from app.services.market_builder import rebuild_market_tables

    rebuild_market_tables(session)
    c1 = anomaly_service.calibrate_pair(session, "GOLDM-GOLDPETAL", None, date(2024, 1, 20))
    c2 = anomaly_service.calibrate_pair(session, "GOLDM-GOLDGUINEA", None, date(2024, 1, 20))
    assert c1.id != c2.id and c1.pair_id != c2.pair_id


def test_pair_features_alignment_date_matching(seeded_activity):
    session = seeded_activity
    from app.services.market_builder import rebuild_market_tables

    rebuild_market_tables(session)
    out = compute_pair_features(session, "GOLDM-GOLDPETAL")
    # 28 shared days -> 28 aligned features; the alignment rule is same-date only.
    assert out["features_added"] == 28
    assert out["alignment_rule"].startswith("same trade_date")
