"""Normalization tests with independently hand-calculated expected values."""
from datetime import date

import pytest

from app.core.errors import NotFound
from app.services.market_builder import contract_inventory, rebuild_market_tables


def _spec(session, symbol, on):
    from app.analytics.normalize import spec_for

    return spec_for(session, symbol, on)


def test_effective_dated_spec_selection(session):
    from app.analytics.normalize import seed_contract_specs

    seed_contract_specs(session)
    s2026 = _spec(session, "GOLDGUINEA", date(2026, 8, 1)).valid_from
    s2025 = _spec(session, "GOLDGUINEA", date(2025, 6, 1)).valid_from
    assert s2026 == date(2026, 7, 1)
    assert s2025 == date(2025, 1, 1)


def test_purity_applied_goldmini(session):
    """GOLDM: quoted per 10 g of 995 purity.

    A 100 g lot worth 151,000 INR: price per quote 15100 -> fine grams per
    quote = 9.95 -> 15175.88 fine/g.
    """
    from app.analytics.normalize import normalize_to_price_per_fine_gram, seed_contract_specs

    seed_contract_specs(session)
    spec = _spec(session, "GOLDM", date(2024, 1, 5))
    value, _ = normalize_to_price_per_fine_gram(151000.0, 100, 10, 995)
    assert round(value, 2) == round(15100 / 9.95, 2)
    assert spec.verification_status == "VERIFIED"


def test_gold_ten_purity_999(session):
    value, _ = 0, 0
    from app.analytics.normalize import normalize_to_price_per_fine_gram

    v, _ = normalize_to_price_per_fine_gram(139000.0, 10, 10, 999)
    assert round(v, 2) == 13913.91  # 139000/9.99


def test_gold_petal_per_gram(session):
    from app.analytics.normalize import normalize_to_price_per_fine_gram

    v, _ = normalize_to_price_per_fine_gram(3139.0, 1, 1, 999)
    assert round(v, 4) == round(3139 / 0.999, 4)


def test_guinea_spec_is_8g_999(session):
    from app.analytics.normalize import seed_contract_specs

    seed_contract_specs(session)
    spec = _spec(session, "GOLDGUINEA", date(2026, 8, 1))
    assert float(spec.trading_unit_grams) == 8
    assert spec.purity_per_mille == 999
    assert spec.quote_rule == "standard_fine"


def test_invalid_inputs_raise(session):
    from app.analytics.normalize import normalize_to_price_per_fine_gram

    with pytest.raises(ValueError):
        normalize_to_price_per_fine_gram(-5, 8, 8, 999)
    with pytest.raises(ValueError):
        normalize_to_price_per_fine_gram(5, 0, 8, 999)


def test_rebuild_market_tables_produces_normalized_values(seeded_activity):
    session = seeded_activity
    out = rebuild_market_tables(session)
    assert out["specs_added"] == 0  # fixture already seeded the four spec versions
    assert out["normalized_added"] >= 28
    from sqlalchemy import select

    from app.models.market import NormalizedPrice, PairFeature

    goldm = session.execute(
        select(NormalizedPrice).where(NormalizedPrice.symbol == "GOLDM",
                                      NormalizedPrice.trade_date == date(2024, 1, 5))
    ).scalar_one()
    # fixture: lots 1005, value_per_lot 131000 -> price/quote = 13100 -> /9.95
    expected = 131000.0 * 10.0 / 100.0 / 9.95
    assert abs(float(goldm.normalized_value) - expected) < 1e-6
    assert goldm.source_status == "PROVISIONAL"


def test_pair_summary_exposes_provisional_status(seeded_activity):
    session = seeded_activity
    rebuild_market_tables(session)
    cards = contract_inventory(session)
    by_symbol = {c["symbol"]: c for c in cards}
    assert by_symbol["GOLDM"]["status"] == "PROVISIONAL"
    assert by_symbol["GOLDTEN"]["data_summary"]["detail_days"] == 28
