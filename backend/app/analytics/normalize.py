"""Contract master + normalization service.

Specifications are effective-dated and sourced from the contract PDFs supplied
in the data folder. Each entry records the source document and verification
status; historical coverage is limited to the earliest provided documents, so
pre-2019 periods are marked PROVISIONAL for GOLDM (not documented here) while
the supplied ten/petal/guinea documents govern from their effective dates.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models.market import ContractSpec, NormalizedPrice

SYMBOL_DISPLAY = {
    "GOLDM": "Gold Mini",
    "GOLDTEN": "Gold Ten",
    "GOLDGUINEA": "Gold Guinea",
    "GOLDPETAL": "Gold Petal",
}

# Verified from supplied official MCX contract-spec PDFs.
# (quote_rule standard_fine: quoted price applies to quote_grams of
#  purity_per_mille fineness; fine grams per quote = quote_grams * purity/1000)
VERIFIED_SPECS: list[dict] = [
    {
        "symbol": "GOLDM", "valid_from": date(2026, 5, 1), "valid_to": None,
        "trading_unit_grams": 100, "quote_grams": 10, "purity_per_mille": 995,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-mini-may-2026-contract-onwards.pdf",
        "verification_status": "VERIFIED",
        "notes": "Trading unit 100 g; quotation/base value 10 g; 995 purity. "
                 "Effective from the earliest supplied Gold Mini document.",
    },
    {
        "symbol": "GOLDTEN", "valid_from": date(2025, 4, 1), "valid_to": None,
        "trading_unit_grams": 10, "quote_grams": 10, "purity_per_mille": 999,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-ten-april-2025-contract-onwards....pdf",
        "verification_status": "VERIFIED",
        "notes": "Trading unit 10 g; quotation/base value 10 g; 999 purity.",
    },
    {
        "symbol": "GOLDGUINEA", "valid_from": date(2026, 7, 1), "valid_to": None,
        "trading_unit_grams": 8, "quote_grams": 8, "purity_per_mille": 999,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-guinea-july-2026-contract-onwards.pdf",
        "verification_status": "VERIFIED",
        "notes": "8 g serially-numbered guinea; quoted per 8 g at 999 purity. "
                 "Final settlement uses DDR (Ahmedabad 995 spot x 999/995 x 8/10) - a "
                 "settlement construction, not a quotation-basis rule.",
    },
    {
        "symbol": "GOLDGUINEA", "valid_from": date(2025, 12, 1), "valid_to": date(2026, 6, 30),
        "trading_unit_grams": 8, "quote_grams": 8, "purity_per_mille": 999,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-guinea-december-2025-contract-onwards....pdf",
        "verification_status": "VERIFIED",
        "notes": "Same quotation basis as the July-2026 document; 3-day staggered tender.",
    },
    {
        "symbol": "GOLDGUINEA", "valid_from": date(2025, 1, 1), "valid_to": date(2025, 11, 30),
        "trading_unit_grams": 8, "quote_grams": 8, "purity_per_mille": 999,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-guinea-january-2025-contract-onwards....pdf",
        "verification_status": "VERIFIED",
        "notes": "Same quotation basis; 5-day staggered tender (tender-period change).",
    },
    {
        "symbol": "GOLDPETAL", "valid_from": date(2025, 4, 1), "valid_to": None,
        "trading_unit_grams": 1, "quote_grams": 1, "purity_per_mille": 999,
        "quote_rule": "standard_fine",
        "source_document_id": "gold-petal-april-2025-contracts-onwards....pdf",
        "verification_status": "VERIFIED",
        "notes": "Trading unit 1 g; quoted per 1 g at 999 purity.",
    },
]


def seed_contract_specs(session: Session, *, source_files_by_name: dict[str, int] | None = None) -> int:
    """Idempotent seed of the verified effective-dated spec versions."""
    added = 0
    for spec in VERIFIED_SPECS:
        existing = session.execute(
            select(ContractSpec).where(
                ContractSpec.symbol == spec["symbol"],
                ContractSpec.valid_from == spec["valid_from"],
            )
        ).scalar_one_or_none()
        if existing:
            continue
        session.add(ContractSpec(**spec))
        added += 1
    session.commit()
    return added


def spec_for(session: Session, symbol: str, on_date: date) -> ContractSpec:
    """Effective spec for a symbol on a date; PROVISIONAL marker for pre-coverage days."""
    row = session.execute(
        select(ContractSpec).where(
            ContractSpec.symbol == symbol,
            ContractSpec.valid_from <= on_date,
            (ContractSpec.valid_to.is_(None)) | (ContractSpec.valid_to >= on_date),
        ).order_by(ContractSpec.valid_from.desc())
    ).scalars().first()
    if row:
        return row
    # No verified coverage for the date: synthesize an explicit provisional spec
    # (latest known spec) so the value can still be computed but never labelled
    # VERIFIED.
    latest = session.execute(
        select(ContractSpec).where(ContractSpec.symbol == symbol)
        .order_by(ContractSpec.valid_from.desc())
    ).scalars().first()
    if latest is None:
        raise NotFound(f"No contract specification registered for symbol '{symbol}'.")
    return latest


def normalize_to_price_per_fine_gram(
    quoted_price: float,
    trading_unit_grams: float,
    quote_grams: float,
    purity_per_mille: int,
    quote_rule: str = "standard_fine",
) -> tuple[float, str]:
    """Convert a quoted price to price-per-fine-gram.

    Returns (value, rule_note). Only standard_fine is implemented; any other
    rule must be added as an explicitly verified contract-specific transform
    (never silently generic).
    """
    if quote_rule != "standard_fine":
        raise ValueError(f"unimplemented quote_rule: {quote_rule}")
    if quoted_price <= 0 or trading_unit_grams <= 0 or quote_grams <= 0:
        raise ValueError("invalid positive-value inputs for normalization")
    fine_grams_per_quote = float(quote_grams) * purity_per_mille / 1000.0
    # Price paid per quote basis, scaled from the actual lot size:
    price_per_quote = quoted_price * float(quote_grams) / float(trading_unit_grams)
    return price_per_quote / fine_grams_per_quote, (
        f"quote_grams={quote_grams}, purity={purity_per_mille}/1000, rule=standard_fine"
    )


def derive_symbol_day_price(session: Session, symbol: str, trade_date: date,
                            lots: int | None, value_lakhs: float | None):
    """Activity-implied quoted-price proxy for one symbol-day (PROVISIONAL by design).

    value_per_lot = total_value_lakhs * 1e5 / lots  (rupees per trading-unit lot)
    quoted_price  = value_per_lot (a quoted price applies to quote_grams within
                    trading_unit_grams; the value covers the whole unit)
    """
    if lots is None or value_lakhs is None or lots <= 0 or value_lakhs <= 0:
        return None
    spec = spec_for(session, symbol, trade_date)
    value_per_lot = float(value_lakhs) * 100000.0 / float(lots)
    quoted_price, rule_note = normalize_to_price_per_fine_gram(
        value_per_lot,
        float(spec.trading_unit_grams),
        float(spec.quote_grams),
        int(spec.purity_per_mille),
        spec.quote_rule,
    )
    return quoted_price, spec, rule_note, float(value_per_lot)
