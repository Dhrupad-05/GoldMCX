"""Walk-forward evaluation report for the trained novelty detector.

An unsupervised novelty detector has no verified ground-truth labels, so
there are NO precision/recall claims here. Reported metrics are honest and
computable: coverage, alert rate per frequency (quarterly walk-forward
epochs), score stability across epochs, and agreement with the analytic
robust-MAD baseline on the most recent holdout block.
"""
from __future__ import annotations

import statistics


def baseline_flags(z_scores, cut: float = 3.5) -> list[int]:
    return [1 if abs(z) > cut else 0 for z in z_scores]


def evaluate(candidate_results: dict, selected: str, holdout_z: list[float],
             model_flag_rate_holdout: float | None = None) -> dict:
    """Assemble the final evaluation payload registered with the artifact."""
    baseline = baseline_flags(holdout_z)
    baseline_rate = (sum(baseline) / len(baseline)) if baseline else 0.0
    selected_summary = candidate_results.get(selected, {})
    agreement = None
    if model_flag_rate_holdout is not None and baseline:
        # Bounded difference in alert behavior; neither metric implies profit.
        agreement = round(abs(model_flag_rate_holdout - baseline_rate), 6)
    return {
        "objective": "contract-aware cross-contract relative-value novelty detection",
        "supervised_metrics_note": (
            "No ground-truth labels exist; no precision/recall/profitability "
            "claims are made. A novelty score is not a probability of profit."
        ),
        "selected_algorithm": selected,
        "baseline": {
            "algorithm": "robust_mad_v1",
            "holdout_flag_rate": round(baseline_rate, 6),
        },
        "selected_holdout_summary": selected_summary,
        "alert_rate_holdout": model_flag_rate_holdout,
        "baseline_flag_rate_agreement": agreement,
        "candidate_comparison": {
            k: {
                "state": v.get("state"),
                "score_stability": round(v["score_stability"], 6)
                if isinstance(v.get("score_stability"), (int, float)) else None,
                "mean_epoch_score": round(v["mean_epoch_score"], 6)
                if isinstance(v.get("mean_epoch_score"), (int, float)) else None,
            }
            for k, v in candidate_results.items() if isinstance(v, dict)
        },
        "epochs": selected_summary.get("epochs") if selected_summary.get("state") == "evaluated" else None,
    }


def quiet_when_unjustified(threshold: float, score: float,
                           cooldown_active: bool = False) -> dict:
    """Explicit quiet rule: a novelty score below threshold is NOT an alert,
    and cooldown suppresses repeat notifications for the same state."""
    if score < threshold or cooldown_active:
        return {"emit_alert": False, "reason": "below_threshold_or_cooldown"}
    return {"emit_alert": True}
