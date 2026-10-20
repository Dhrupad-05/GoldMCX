"""Canonical pair contract: six unique pairs, order-independence, legacy alias,
explicit unknown-id errors (no silent fallback to a different pair)."""
import pytest

from app.core.errors import InvalidInput, NotFound
from app.core.pairs import (
    CANONICAL_PAIRS,
    LEGACY_PAIR_ALIASES,
    PAIR_IDS,
    canonical_pair_id,
    orient,
    pair_members,
    resolve_pair_id,
)


def test_six_unique_canonical_pairs():
    assert len(PAIR_IDS) == 6
    assert len(set(PAIR_IDS)) == 6


def test_order_independent_lookup():
    assert canonical_pair_id("GOLDPETAL", "GOLDM") == "GOLDM-GOLDPETAL"
    assert canonical_pair_id("GOLDM", "GOLDPETAL") == "GOLDM-GOLDPETAL"
    assert resolve_pair_id("GOLDPETAL-GOLDM") == "GOLDM-GOLDPETAL"


def test_legacy_alias_maps_to_guinea_petal():
    assert LEGACY_PAIR_ALIASES["REST-GOLDPETAL"] == "GOLDGUINEA-GOLDPETAL"
    assert resolve_pair_id("REST-GOLDPETAL") == "GOLDGUINEA-GOLDPETAL"


def test_unknown_pair_raises_not_found():
    with pytest.raises(NotFound):
        resolve_pair_id("GOLDM-GOLD")  # unknown symbol, not silently another pair
    with pytest.raises(NotFound):
        resolve_pair_id(" completely-bogus")


def test_same_symbol_rejected_and_no_seventh_pair():
    with pytest.raises(InvalidInput):
        canonical_pair_id("GOLDM", "GOLDM")


def test_orient_normalizes_to_alphabetical():
    a, b = orient("GOLDM-GOLDPETAL", "GOLDPETAL", "GOLDM")
    assert (a, b) == ("GOLDM", "GOLDPETAL")


def test_pair_members_validates():
    with pytest.raises(NotFound):
        pair_members("NOT-A-PAIR")
