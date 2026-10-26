"""Temporal novelty training / model selection for daily pair observations.

Design decisions (documented so results are interpretable):
- Candidates: IsolationForest (scalable default) benchmarked against
  OneClassSVM normality modeling. The selected estimator is chosen by holdout
  score stability, never by "flags more anomalies".
- The dataset is NOT shuffled: chronological walk-forward validation only.
- Presumed-normal training subset: causal robust-z rule only (|z| > 3.5 on
  the strictly past rolling window); every exclusion is reported, never
  hidden. Day t never feeds its own window.
- Scalers are fit ONLY on the training partition and ship inside the fitted
  sklearn Pipeline stored in the artifact.
- Thresholds are calibrated from training-period scores at a contamination
  quantile; the analytic robust-MAD baseline remains the documented fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CONTAMINATION = 0.04
MIN_TRAIN_ROWS = 60
BASELINE_NOTE = "robust-MAD (|z|>3.5) is kept as the documented analytic fallback"


class TrainDataError(Exception):
    """Insufficient presumed-normal data for fitting; message is actionable."""


@dataclass
class TrainResult:
    algorithm: str
    algorithm_version: str
    pipeline_version: str = "novelty_v1"
    train_rows: int = 0
    excluded_from_train: int = 0
    threshold: float = 0.0
    evaluation: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _isolation_forest_pipeline():
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import RobustScaler

    return Pipeline([
        ("scaler", RobustScaler()),
        ("estimator", IsolationForest(
            n_estimators=300, contamination=CONTAMINATION, random_state=42,
        )),
    ])


def _one_class_svm_pipeline():
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import RobustScaler
    from sklearn.svm import OneClassSVM

    return Pipeline([
        ("scaler", RobustScaler()),
        ("estimator", OneClassSVM(nu=CONTAMINATION * 3, kernel="rbf", gamma="scale")),
    ])


def presumed_normal_rows(X, z_feature: str = "rolling_z_20", z_abs_cut: float = 3.5):
    """Indices kept for presumed-normal training + exclusion count.

    The cut uses only the CAUSAL rolling-z feature, so deciding whether a row
    joins training never peeks at that row's own future.
    """
    from ml.features import FEATURE_NAMES

    z_idx = list(FEATURE_NAMES).index(z_feature)
    kept, excluded = [], 0
    for i, row in enumerate(X):
        if abs(row[z_idx]) > z_abs_cut:
            excluded += 1
            continue
        kept.append(i)
    return kept, excluded


def walk_forward(estimator_factory, X, train_frac: float = 0.6) -> dict:
    """Fit on the past, score the next chronological block; epochs joined."""
    import numpy as np

    n = len(X)
    train_end = int(n * train_frac)
    if train_end < MIN_TRAIN_ROWS:
        return {"state": "skipped", "detail": f"insufficient rows ({train_end} < {MIN_TRAIN_ROWS})"}
    Xa = np.asarray(X, dtype=float)
    block = max(20, (n - train_end) // 4)
    epochs = []
    for start in range(train_end, n, block):
        end = min(start + block, n)
        if end <= start:
            break
        est = estimator_factory()
        est.fit(Xa[:start])
        scores = -est.score_samples(Xa[start:end])
        epochs.append({
            "train_end_idx": start,
            "n_scored": end - start,
            "mean_score": float(np.mean(scores)),
            "max_score": float(np.max(scores)),
        })
    import statistics

    means = [e["mean_score"] for e in epochs]
    return {
        "state": "evaluated",
        "epochs": len(epochs),
        "mean_epoch_score": float(statistics.mean(means)),
        "score_stability": float(statistics.pstdev(means)) if len(means) > 1 else 0.0,
        "n": n, "train_end": train_end,
    }


def candidate_scores(X) -> dict:
    """Evaluate every candidate via walk-forward; report, never cherry-pick."""
    return {
        "presumed_normal_excluded_info": presumed_normal_rows(X),
        "iforest": walk_forward(_isolation_forest_pipeline, X),
        "one_class_svm": walk_forward(_one_class_svm_pipeline, X),
        "baseline_note": BASELINE_NOTE,
    }


def select_candidate(candidates: dict) -> str:
    """Most temporally-stable holdout wins; IsolationForest when ties/skip."""
    options = {
        k: v for k, v in candidates.items()
        if isinstance(v, dict) and v.get("state") == "evaluated"
    }
    if "iforest" not in options:
        return "iforest"
    if "one_class_svm" in options:
        if options["one_class_svm"]["score_stability"] < options["iforest"]["score_stability"] * 0.8:
            return "one_class_svm"
    return "iforest"


def fit_final_model(X, algorithm: str) -> dict:
    """Fit the final pipeline on the presumed-normal training partition ONLY.

    The scaler/estimator fit happens strictly on the kept rows; inference
    never refits. Threshold derives from training-period scores.
    """
    import numpy as np

    kept, excluded = presumed_normal_rows(X)
    if len(kept) < MIN_TRAIN_ROWS:
        raise TrainDataError(
            f"presumed-normal subset too small after exclusions "
            f"({len(kept)} rows < {MIN_TRAIN_ROWS}); sync more verified history."
        )
    X_train = np.asarray([X[i] for i in kept], dtype=float)
    factory = _isolation_forest_pipeline if algorithm == "iforest" else _one_class_svm_pipeline
    pipeline = factory()
    pipeline.fit(X_train)
    inlier_scores = -pipeline.score_samples(X_train)
    threshold = float(np.quantile(inlier_scores, 1 - CONTAMINATION))
    return {
        "pipeline": pipeline,
        "algorithm": algorithm,
        "algorithm_version": "1",
        "train_rows": len(kept),
        "excluded_from_train": excluded,
        "threshold": threshold,
        "contamination": CONTAMINATION,
    }
