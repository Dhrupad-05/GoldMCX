"""Inference: load the ACTIVE registered artifact and score observations.

Safety rules enforced here:
- The active artifact URI comes ONLY from trusted DB metadata (never from a
  request), is resolved under the configured artifact root, and its SHA-256
  plus feature schema are re-verified at load time.
- Mismatched checksum, bundle version, feature names or incompatible sklearn
  versions refuse to score (ModelUnavailable), surfacing a model-unavailable
  state rather than silently degrading.
- The loaded pipeline is cached per (path, sha256); upgrades swap only after
  the new artifact passes validation.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session


class ModelUnavailable(Exception):
    """Active artifact missing/corrupt/schema-mismatch: scoring must stop."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class LoadedModel:
    model_version: str
    mode: str
    pipeline: object
    feature_names: list
    threshold: float
    algorithm: str
    severity_bands: dict


def artifact_root() -> Path:
    """Persistent artifact directory: ML_ARTIFACT_DIR or ml/artifacts/."""
    configured = os.environ.get("ML_ARTIFACT_DIR")
    base = Path(__file__).resolve().parent
    return Path(configured) if configured else (base / "artifacts")


def resolve_under_root(path_str: str) -> Path:
    """Resolve a registry path strictly under artifact_root (no traversal)."""
    root = artifact_root().resolve()
    p = (Path(path_str) if os.path.isabs(path_str) else root / path_str).resolve()
    if root != p and root not in p.parents:
        raise ModelUnavailable("registered artifact path escapes the trusted root")
    return p


def get_active_row(session: Session, mode: str = "daily"):
    from app.models.ml_registry import select_active_stmt

    return session.execute(select_active_stmt(mode)).scalars().first()


@lru_cache(maxsize=8)
def _load_bundle(path_str: str, sha256: str):
    import joblib

    path = resolve_under_root(path_str)
    if not path.exists():
        raise ModelUnavailable(f"artifact file missing: {path.name}")
    digest = _sha256_of(path)
    if digest != sha256:
        raise ModelUnavailable("artifact checksum mismatch: refusing to score")
    bundle = joblib.load(path)
    if bundle.get("bundle_version") != "1":
        raise ModelUnavailable(f"unsupported bundle version {bundle.get('bundle_version')}")
    return bundle


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_active(session: Session, mode: str = "daily") -> LoadedModel:
    row = get_active_row(session, mode)
    if row is None:
        raise ModelUnavailable("no active trained model registered")
    try:
        bundle = _load_bundle(row.artifact_path, row.artifact_sha256)
    except ModelUnavailable:
        raise
    if list(bundle.get("feature_names", [])) != list(row.feature_names):
        raise ModelUnavailable("feature schema mismatch between artifact and registry")
    _check_sklearn_compat(bundle)
    return LoadedModel(
        model_version=row.model_version,
        mode=row.mode,
        pipeline=bundle["pipeline"],
        feature_names=bundle["feature_names"],
        threshold=float(bundle["threshold"]),
        algorithm=bundle["algorithm"],
        severity_bands=bundle.get("severity_bands") or {},
    )


def _check_sklearn_compat(bundle: dict) -> None:
    import sklearn

    required = (bundle.get("package_versions") or {}).get("scikit-learn")
    if not required:
        return
    if required.split(".")[:2] != sklearn.__version__.split(".")[:2]:
        raise ModelUnavailable(
            f"artifact trained with scikit-learn {required}; runtime has {sklearn.__version__}"
        )


def score_observation(model: LoadedModel, feature_vector: list[float]) -> dict:
    """Score one validated ordered feature vector; threshold + severity bands."""
    import numpy as np

    if len(feature_vector) != len(model.feature_names):
        raise ModelUnavailable("feature vector length mismatch")
    X = np.asarray([feature_vector], dtype=float)
    raw = float(-model.pipeline.score_samples(X)[0])
    is_anomaly = raw >= model.threshold
    severity = "Normal"
    if is_anomaly:
        severity = _severity(raw, model.threshold, model.severity_bands)
    in_band = {
        "raw_score": round(raw, 8),
        "threshold": round(model.threshold, 8),
        "is_anomaly": is_anomaly,
        "severity": severity,
        "model_version": model.model_version,
        "feature_names": model.feature_names,
        "feature_values": dict(zip(model.feature_names, [float(v) for v in feature_vector])),
        "note": "novelty score is not a probability of profit",
    }
    return in_band


def _severity(raw: float, threshold: float, bands: dict) -> str:
    high = float(bands.get("high", 1.3))
    if raw >= threshold * high:
        return "High"
    return "Watch"


def model_status(session: Session, mode: str = "daily") -> dict:
    """Honest model readiness for API/UI surfacing."""
    from app.models.ml_registry import TrainedModel
    from sqlalchemy import select

    rows = (
        session.execute(
            select(TrainedModel)
            .where(TrainedModel.mode == mode)
            .order_by(TrainedModel.created_at.desc())
            .limit(10)
        ).scalars().all()
    )
    active = next((r for r in rows if r.status == "active"), None)
    status = "NOT_READY" if active is None else "READY"
    payload = {
        "mode": mode,
        "status": status,
        "model_version": active.model_version if active else None,
        "algorithm": active.algorithm if active else None,
        "feature_names": active.feature_names if active else None,
        "artifact_path": active.artifact_path if active else None,
        "artifact_sha256": active.artifact_sha256 if active else None,
        "evaluation": active.evaluation if active else None,
        "notes": active.notes if active else None,
        "registry": [
            {
                "model_version": r.model_version,
                "status": r.status,
                "algorithm": r.algorithm,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "activated_at": r.activated_at.isoformat() if r.activated_at else None,
            }
            for r in rows
        ],
    }
    if active is not None:
        try:
            load_active(session, mode)
        except ModelUnavailable as exc:
            payload["status"] = "UNAVAILABLE"
            payload["notes"] = f"active artifact failed validation: {exc.reason}"
    return payload
