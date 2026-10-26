"""Contract-aware relative-value feature computation.

One versioned feature schema is used by BOTH training and inference
(test-enforced parity). Features are pair-relative and causal:

- Normalization uses the effective-dated ContractSpec quote basis:
  value_per_fine_gram = close_price / (quote_grams * purity_per_mille / 1000).
- spread_pct follows the SAME formula as the backend analytics layer:
  (a - b) / mid * 100.
- Rolling statistics are strictly causal (windows end at t-1; day t never
  contributes to its own window), so no leakage and no centered windows.
- Expiry is real: observations carry the actual contract expiry of each leg;
  contracts roll as new series (roll boundaries are flagged, never smoothed).
- Missing pair legs produce NO observation (no forward-fill, ever).
"""
from __future__ import annotations

import math
import statistics
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.normalize import spec_for
from app.models.live import ProviderDailyBar
from app.providers.base import CANONICAL_SYMBOLS
from app.core.pairs import pair_members
from app.models.market import ContractSpec  # noqa: F401 (typed surface)

FEATURE_VERSION = "mldaily_v1"
BUNDLE_VERSION = "1"

FEATURE_NAMES: tuple[str, ...] = (
    "spread_pct",
    "spread_change_pct",
    "log_ratio",
    "rolling_z_20",
    "rolling_vol_20",
    "dte_left",
    "dte_right",
    "dte_diff",
    "log_volume_ratio",
    "volume_missing",
    "is_roll_boundary_last",
)

ROLL_WINDOW = 20


def value_per_fine_gram(close: float, spec: ContractSpec) -> float:
    """Contract-aware normalized value (INR per fine gram), manual-verified."""
    fine = float(spec.quote_grams) * int(spec.purity_per_mille) / 1000.0
    return close / fine


def front_contract_bars(session: Session, symbol: str) -> dict[date, ProviderDailyBar]:
    """Roll-aware series: per trade date, the nearest-expiry contract quoted.

    A contract keeps its own expiry; when the front contract rolls, the
    boundary is captured (flagged downstream) instead of stitched silently.
    Rows come ONLY from persisted, validated ProviderDailyBar records.
    """
    rows = session.execute(
        select(ProviderDailyBar)
        .where(ProviderDailyBar.symbol == symbol, ProviderDailyBar.data_status != "QUARANTINED")
        .order_by(ProviderDailyBar.trade_date, ProviderDailyBar.expiry_date)
    ).scalars().all()
    front: dict[date, ProviderDailyBar] = {}
    for r in rows:
        if r.expiry_date is None or r.expiry_date < r.trade_date:
            continue  # expired contract is not tradable that day
        prev = front.get(r.trade_date)
        if prev is None or r.expiry_date < prev.expiry_date:
            front[r.trade_date] = r
    return front


def build_symbol_values(session: Session, symbol: str) -> dict[date, dict]:
    """Per-date normalized per-fine-gram values + volumes for one symbol."""
    out: dict[date, dict] = {}
    for trade_date, bar in front_contract_bars(session, symbol).items():
        spec = spec_for(session, symbol, trade_date)
        close = float(bar.close) if bar.close is not None else None
        if close is None or close <= 0:
            continue
        if spec is None:
            # No verified effective-dated spec: the row is excluded, not guessed.
            continue
        out[trade_date] = {
            "value_per_fine_gram": value_per_fine_gram(close, spec),
            "expiry_date": bar.expiry_date,
            "volume": float(bar.volume) if bar.volume is not None else None,
            "open_interest": (
                float(bar.open_interest) if bar.open_interest is not None else None
            ),
            "close": close,
            "provider": bar.provider,
            "spec_id": spec.id,
        }
    return out


def _causal_robust_stats(values: list[float]) -> tuple[float, float]:
    """Median and MAD of a strictly PAST window (used at t on values < t)."""
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    if mad <= 0:
        mad = statistics.stdev(values) if len(values) > 1 else 0.0
    if mad <= 0:
        mad = 1e-6
    return med, mad


def _log_volume_ratio(vl, vr) -> float:
    if vl and vr and vl > 0 and vr > 0:
        return round(float(math.log(vl / vr)), 8)
    return 0.0


def build_pair_observations(session: Session, pair_id: str) -> dict:
    """Aligned daily observations for one canonical pair with lineage."""
    left_sym, right_sym = pair_members(pair_id)
    left = build_symbol_values(session, left_sym)
    right = build_symbol_values(session, right_sym)
    common = sorted(set(left) & set(right))

    exclusions: dict[str, int] = {
        "dates_missing_left_leg": len(set(left) ^ set(right) & set(left)),
        "dates_missing_right_leg": (len(set(left)) - len(common)),
        "dates_missing_left_leg_total": 0,
    }
    exclusions = {
        "dates_only_right_leg": len(set(right) - set(left)),
        "dates_only_left_leg": len(set(left) - set(right)),
        "paired_common_dates": len(common),
    }

    observations: list[dict] = []
    spreads: list[float] = []
    prev_spread: float | None = None
    prev_date: date | None = None
    prev_expiry_left: date | None = None
    prev_expiry_right: date | None = None

    for d in common:
        le = left[d]
        re_ = right[d]
        a, b = le["value_per_fine_gram"], re_["value_per_fine_gram"]
        if a <= 0 or b <= 0:
            continue
        mid = (a + b) / 2.0
        spread = (a - b) / mid * 100.0

        roll_left = 1 if (prev_expiry_left is not None and le["expiry_date"] != prev_expiry_left) else 0
        roll_right = (
            1 if (prev_expiry_right is not None and re_["expiry_date"] != prev_expiry_right) else 0
        )
        is_roll_boundary = 1 if (roll_left or roll_right) else 0

        # Causal rolling stats strictly over PAST observations.
        window = spreads[-ROLL_WINDOW:]
        med, mad = _causal_robust_stats(window)
        z = (spread - med) / mad if len(window) >= ROLL_WINDOW else 0.0
        vol = mad if window else 0.0

        # Change features are suspended across contract rolls.
        change = None
        if prev_spread is not None and not is_roll_boundary:
            change = spread - prev_spread

        gap = (d - prev_date).days if prev_date is not None else 0
        significant_gap = gap > 7  # multi-week hole: never treat as adjacent

        dte_left = (le["expiry_date"] - d).days
        dte_right = (re_["expiry_date"] - d).days

        observations.append({
            "pair_id": pair_id,
            "trade_date": d,
            "left_symbol": left_sym,
            "right_symbol": right_sym,
            "expiry_left": le["expiry_date"].isoformat(),
            "expiry_right": re_["expiry_date"].isoformat(),
            "left_value": round(a, 6),
            "right_value": round(b, 6),
            "spread_pct": round(spread, 8),
            "spread_change_pct": round(change, 8) if change is not None else None,
            "log_ratio": round(float(math.log(a / b)), 8),
            "rolling_z_20": round(z, 8),
            "rolling_vol_20": round(vol, 8),
            "dte_left": dte_left,
            "dte_right": dte_right,
            "dte_diff": dte_left - dte_right,
            "log_volume_ratio": _log_volume_ratio(le["volume"], re_["volume"]),
            "volume_missing": 1 if (le["volume"] is None or re_["volume"] is None) else 0,
            "is_roll_boundary_last": is_roll_boundary,
            "significant_calendar_gap": significant_gap,
            "source_status": "VERIFIED"
            if le["provider"] == "mcx_bhavcopy" and re_["provider"] == "mcx_bhavcopy"
            else "PROVISIONAL",
            "providers": [le["provider"], re_["provider"]],
            "feature_version": FEATURE_VERSION,
        })
        spreads.append(spread)
        prev_spread = spread
        prev_date = d
        prev_expiry_left = le["expiry_date"]
        prev_expiry_right = re_["expiry_date"]

    return {
        "pair_id": pair_id,
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "observations": observations,
        "exclusions": exclusions,
        "alignment_rule": "same trade_date inner join of front contracts; no forward-fill",
    }


def feature_vector(obs: dict) -> list[float]:
    """Deterministic ordered feature vector in FEATURE_NAMES order."""
    out = []
    for name in FEATURE_NAMES:
        v = obs.get(name)
        out.append(float(v) if v is not None else 0.0)
    return out


def eligible_symbols() -> tuple[str, ...]:
    return CANONICAL_SYMBOLS
