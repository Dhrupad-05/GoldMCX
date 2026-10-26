"""Validated historical dataset assembly for ML training.

Combines canonical pair observations from PROVIDER/EOD bars only. Activity
reports (aggregated lots/value) are never admitted to the verified dataset:
a row sourced from activity imputation carries source_status PROVISIONAL and
is excluded from training.

The builder reports every exclusion with a reason; when the validated history
is too thin for training it FAILS loudly (TrainDataError) instead of
synthesizing rows.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pairs import PAIR_IDS
from ml.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_pair_observations,
    feature_vector,
)

MIN_OBS_PER_PAIR = 60      # training floor: fewer verified pairs -> DATA TOO THIN
MIN_TOTAL_FOR_TRAIN = 300  # absolute floor across pairs per pair-block


class TrainDataError(Exception):
    """Insufficient verified data for training; message is operator-actionable."""


def dataset(session: Session, pairs: list[str] | None = None,
            end_date: date | None = None, start_date: date | None = None) -> dict:
    """Build and validate the training dataset for the given canonical pairs."""
    pairs = pairs or list(PAIR_IDS)
    blocks: dict[str, dict] = {}
    total_rows = 0
    coverage: dict[str, dict] = {}
    providers: dict[str, int] = {}
    for pair_id in pairs:
        built = build_pair_observations(session, pair_id)
        obs = built["observations"]
        if start_date is not None:
            obs = [o for o in obs if o["trade_date"] >= start_date]
        if end_date is not None:
            obs = [o for o in obs if o["trade_date"] <= end_date]
        blocks[pair_id] = built
        total_rows += len(obs)
        for o in obs:
            for p in o["providers"]:
                providers[p] = providers.get(p, 0) + 1
        coverage[pair_id] = {
            "rows": len(obs),
            "exclusions": built["exclusions"],
            "first_date": obs[0]["trade_date"].isoformat() if obs else None,
            "last_date": obs[-1]["trade_date"].isoformat() if obs else None,
        }

    thin_pairs = [p for p, c in coverage.items() if c["rows"] < MIN_OBS_PER_PAIR]
    quality_report = {
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "pairs": coverage,
        "provider_mix": providers,
        "policy": (
            "verified/provisional provider bars only; activity-implied pseudo "
            "prices are never used; missing legs excluded; no forward-fill"
        ),
    }
    if total_rows < MIN_TOTAL_FOR_TRAIN:
        raise TrainDataError(
            f"Insufficient verified history for training: {total_rows} usable "
            f"pair-observations (need >= {MIN_TOTAL_FOR_TRAIN}). Thin pairs: {thin_pairs}. "
            "Run an EOD/provider sync first — the platform does not fabricate data."
        )
    return {
        "total_rows": total_rows,
        "blocks": blocks,
        "coverage": coverage,
        "quality_report": quality_report,
    }


def feature_matrix(blocks: dict) -> tuple[list[list[float]], list[dict], list[str]]:
    """Ordered vector matrix + aligned observation rows + feature names."""
    rows_X: list[list[float]] = []
    rows_meta: list[dict] = []
    for pair_id in sorted(blocks):
        for obs in blocks[pair_id]["observations"]:
            rows_X.append(feature_vector(obs))
            rows_meta.append(obs)
    return rows_X, rows_meta, list(FEATURE_NAMES)


def fingerprint(blocks: dict) -> str:
    """Deterministic dataset fingerprint for lineage/registration."""
    import hashlib
    import json

    parts = []
    for pair_id in sorted(blocks):
        for obs in blocks[pair_id]["observations"]:
            parts.append(json.dumps([
                obs["pair_id"], str(obs["trade_date"]), obs["expiry_left"],
                obs["expiry_right"], obs["spread_pct"], obs["left_value"],
                obs["right_value"], obs["providers"],
            ], sort_keys=True))
    basis = "|".join(parts)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def dataset_bar_count(session: Session) -> int:
    """Count persisted provider daily bars (the raw verified layer)."""
    from app.models.live import ProviderDailyBar

    return int(
        session.execute(
            select(func.count()).select_from(ProviderDailyBar)
        ).scalar_one()
    )
