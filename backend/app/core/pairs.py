"""Canonical contract/pair domain: pure logic, shared by storage, APIs, analytics.

Canonical pair identifiers are alphabetical, deterministic, and independent of
request ordering. A legacy frontend alias is translated here only at adapter
boundaries; storage and analytics always use the canonical id.
"""
from app.core.errors import InvalidInput, NotFound

SYMBOLS = ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL")

# Six canonical unordered pairs, alphabetical orientation.
CANONICAL_PAIRS: tuple[tuple[str, str], ...] = (
    ("GOLDM", "GOLDTEN"),
    ("GOLDM", "GOLDGUINEA"),
    ("GOLDM", "GOLDPETAL"),
    ("GOLDTEN", "GOLDGUINEA"),
    ("GOLDTEN", "GOLDPETAL"),
    ("GOLDGUINEA", "GOLDPETAL"),
)

PAIR_IDS: tuple[str, ...] = tuple(f"{a}-{b}" for a, b in CANONICAL_PAIRS)

# Legacy frontend identifier (typo) mapped to its canonical pair.
LEGACY_PAIR_ALIASES: dict[str, str] = {
    "REST-GOLDPETAL": "GOLDGUINEA-GOLDPETAL",
}


def canonical_pair_id(a: str, b: str) -> str:
    """Deterministic canonical id for an unordered pair of valid symbols."""
    _require_symbol(a)
    _require_symbol(b)
    if a == b:
        raise InvalidInput(f"Cannot form a pair from the same symbol: {a}.")
    key = "-".join(sorted((a, b)))
    if key not in PAIR_IDS:
        raise InvalidInput(f"Pair '{a}-{b}' is not one of the six canonical pairs.")
    return key


def resolve_pair_id(pair_id: str) -> str:
    """Resolve a pair identifier (or legacy alias) to the canonical id.

    Accepts both orientations (order-independent lookup) and rejects
    genuinely unknown ids with NotFound - never falls back to an unrelated
    pair.
    """
    if pair_id in PAIR_IDS:
        return pair_id
    if pair_id in LEGACY_PAIR_ALIASES:
        return LEGACY_PAIR_ALIASES[pair_id]
    parts = pair_id.split("-")
    if len(parts) == 2:
        a, b = sorted(parts)
        if f"{a}-{b}" in PAIR_IDS:
            return f"{a}-{b}"
    raise NotFound(
        f"Unknown pair id '{pair_id}'. Valid canonical ids: {', '.join(PAIR_IDS)} "
        "(legacy alias 'REST-GOLDPETAL' is accepted)."
    )


def orient(canonical_id: str, left: str, right: str) -> tuple[str, str]:
    """Orient (left, right) to the canonical (alphabetical) orientation."""
    _require_symbol(left)
    _require_symbol(right)
    if left == right:
        raise InvalidInput(f"Cannot orient a pair of the same symbol: {left}.")
    a, b = canonical_id.split("-")
    if {left, right} != {a, b}:
        raise InvalidInput(f"Symbols {left}, {right} do not form canonical pair {canonical_id}.")
    return (left, right) if left < right else (right, left)


def _require_symbol(s: str) -> None:
    if s not in SYMBOLS:
        raise NotFound(
            f"Unknown symbol '{s}'. Valid symbols: {', '.join(SYMBOLS)}."
        )


def require_symbol(s: str) -> None:
    _require_symbol(s)


def resolve_pair_id_or_none(pair_id: str | None) -> str | None:
    if pair_id is None:
        return None
    return resolve_pair_id(pair_id)


def pair_members(canonical_id: str) -> tuple[str, str]:
    if canonical_id not in PAIR_IDS:
        raise NotFound(f"Unknown canonical pair id '{canonical_id}'.")
    a, b = canonical_id.split("-")
    return a, b
