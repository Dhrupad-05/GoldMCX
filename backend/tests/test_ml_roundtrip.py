"""ML pipeline acceptance: training on synthesized-but-valid feature matrices,
artifact registration, checksum/schema gating, and honest run statuses."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    return tmp_path


def _synthetic_rows(n: int = 160) -> list[list[float]]:
    """Deterministic, presumed-normal-ish feature rows in FEATURE_NAMES order.

    Only the CORRECT (causal) rolling-z column may be nonzero beyond noise:
    presumed_normal_rows() gates on it exactly like training does.
    """
    from ml.features import FEATURE_NAMES

    rng = np.random.default_rng(11)
    rows = []
    for i in range(n):
        row = [float(round(rng.normal(0.0, 0.02), 6)) for _ in FEATURE_NAMES]
        z_idx = list(FEATURE_NAMES).index("rolling_z_20")
        row[z_idx] = float(round(rng.normal(0.0, 0.4), 6))
        rows.append(row)
    return rows


def _register_active(session, X, tmp_path: Path) -> str:
    import joblib

    from ml.train import fit_final_model
    from ml.train_model import build_bundle, register_model

    fitted = fit_final_model(X, "iforest")
    bundle = build_bundle(
        fitted=fitted,
        feature_names=fitted["pipeline"].feature_names_in_
        if hasattr(fitted["pipeline"], "feature_names_in_") else list(X[0]),
        evaluation={"state": "evaluated", "epochs": 2},
        quality_report={"excluded": fitted["excluded_from_train"]},
        data_sha="deadbeef" * 8,
        train_window=(date(2026, 1, 1), date(2026, 2, 1)),
        sample_counts=(len(X), fitted["train_rows"]),
    )
    adir = Path(os.environ["ML_ARTIFACT_DIR"])
    adir.mkdir(parents=True, exist_ok=True)
    path = adir / "art_daily.joblib"
    tmp = path.with_suffix(".tmp")
    joblib.dump(bundle, tmp)
    os.replace(tmp, path)  # atomic publication

    import hashlib

    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return register_model(session, bundle, str(path), sha)


def test_train_fit_uses_only_presumed_normal_rows():
    from ml.features import FEATURE_NAMES
    from ml.train import presumed_normal_rows

    X = _synthetic_rows(120)
    # force a few extreme causal z outliers to be excluded
    z_idx = list(FEATURE_NAMES).index("rolling_z_20")
    for i in (3, 40, 80):
        X[i][z_idx] = 5.0
    kept, excluded = presumed_normal_rows(X)
    assert excluded == 3
    assert 3 not in kept and 117 == len(kept)  # 120 - 3 exclusions


def test_entrypoint_insufficient_history_fails_explicitly(session):
    from ml.dataset import TrainDataError, dataset

    with pytest.raises(TrainDataError):
        dataset(session)


def test_bundle_round_trip_through_registry_and_inference(session):
    from ml.inference import load_active, score_observation

    X = _synthetic_rows(160)
    mv = _register_active(session, X, Path(os.environ["ML_ARTIFACT_DIR"]))
    session.commit()

    model = load_active(session, "daily")
    assert model.model_version == mv
    assert model.algorithm == "iforest"
    assert len(model.feature_names) == len(X[0])

    result = score_observation(model, X[0])
    assert result["model_version"] == mv
    for key in ("raw_score", "threshold", "is_anomaly", "severity", "feature_values"):
        assert key in result
    assert 0 <= result["raw_score"]


def test_checksum_mismatch_refuses_to_score(session):
    from ml.inference import ModelUnavailable, load_active

    X = _synthetic_rows(160)
    _register_active(session, X, Path(os.environ["ML_ARTIFACT_DIR"]))
    session.commit()

    from app.models.ml_registry import TrainedModel
    from sqlalchemy import update

    session.execute(
        update(TrainedModel).values(artifact_sha256="0" * 64)
    )
    session.commit()

    with pytest.raises(ModelUnavailable) as exc:
        load_active(session, "daily")
    assert "checksum" in exc.value.reason


def test_registered_path_outside_the_trusted_root_is_refused(session):
    from ml.inference import ModelUnavailable, load_active

    X = _synthetic_rows(160)
    _register_active(session, X, Path(os.environ["ML_ARTIFACT_DIR"]))
    session.commit()

    from app.models.ml_registry import TrainedModel

    row = session.query(TrainedModel).order_by(TrainedModel.id.desc()).first()
    row.artifact_path = "C:/elsewhere/evil.joblib"
    session.commit()

    with pytest.raises(ModelUnavailable) as exc:
        load_active(session, "daily")
    assert "trusted root" in exc.value.reason


def test_daily_job_reports_honest_not_ready_without_model_or_data(session):
    """No providers configured + empty history: the scheduled job records a run
    and explicitly refuses to score or fabricate anything."""
    from ml.jobs import run_daily_job

    summary = run_daily_job(session)
    assert str(summary["status"]).startswith("completed")
    assert summary["scoring"] is None
    assert "Insufficient" in summary["scoring_blocker"]
    sync = summary["sync"]
    assert all(v["state"] == "not_configured" for v in sync.values())

    from app.models.evaluation import AnomalyScore
    from sqlalchemy import select

    assert session.execute(select(AnomalyScore)).scalars().first() is None
