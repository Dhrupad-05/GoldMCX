"""Row-level classification and validation for activity-report tables.

Classification is content-based: headers and cell values decide the class.
Activity rows never become futures OHLC; OPTFUT never enters futures activity.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.ingestion.constants import TARGET_SYMBOLS

MONTHS = {
    m: i + 1 for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})")


def is_date_format_header(headers: list[str]) -> bool:
    """DateWise reports use Instrument/Date/... headers (detail includes Segment/Commodity)."""
    norm = [h.lower().replace(" ", "") for h in headers]
    has_instrument = any(h.startswith("instrument") for h in norm)
    has_date = any(h == "date" for h in norm)
    has_lots = any(h.startswith("tradedcontract") for h in norm)
    has_value = any(h.startswith("totalvalue") for h in norm)
    return has_instrument and has_date and has_lots and has_value


def parse_report_date(cell: str) -> date | None:
    m = _DATE_RE.search(cell.strip())
    if not m:
        return None
    d, mon, y = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
    if mon not in MONTHS:
        return None
    try:
        return date(y, MONTHS[mon], d)
    except ValueError:
        return None


def parse_int(cell: str) -> int | None:
    s = cell.replace(",", "").strip()
    if s in ("", "-"):
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    return None


def parse_decimal(cell: str) -> float | None:
    s = cell.replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def classify_and_validate_row(
    header_map: dict[str, int],
    cells: list[str],
    source_class_hint: str,
) -> dict:
    """Return a validated row payload or raise ValueError with a quarantinable reason."""
    def cell(field: str) -> str:
        idx = header_map.get(field)
        return cells[idx].strip() if idx is not None and idx < len(cells) else ""

    instrument = cell("Instrument").upper()
    if instrument not in ("FUTCOM", "OPTFUT"):
        raise ValueError(f"unsupported instrument: {instrument!r}")

    trade_date = parse_report_date(cell("Date"))
    if trade_date is None:
        raise ValueError(f"invalid or missing trade date: {cell('Date')!r}")

    commodity = cell("Commodity").upper()
    symbol = commodity if commodity in TARGET_SYMBOLS else instrument and commodity
    if not commodity:
        # Summary reports have no Commodity column; the folder identity supplies Symbol.
        symbol = source_class_hint
    elif commodity not in TARGET_SYMBOLS:
        raise ValueError(f"unknown commodity: {commodity!r}")

    lots = parse_int(cell("Traded Contract (Lots)"))
    total_value = parse_decimal(cell("Total Value (Lakhs)"))
    premium_value = parse_decimal(cell("Premium Value (Lakhs)")) if premium_field(header_map) else None
    turnover = parse_decimal(cell("Avg Daily Turnover(Lakhs)")) if turnover_field(header_map) else None

    if lots is None and total_value is None:
        raise ValueError("row has neither lots nor total value (empty activity)")

    if lots is not None and lots == 0 and total_value is not None and total_value > 0:
        raise ValueError("inconsistent row: zero lots with positive value")

    if lots is not None and lots < 0:
        raise ValueError("negative lots")
    if total_value is not None and total_value < 0:
        raise ValueError("negative total value")

    payload = {
        "instrument": instrument,
        "trade_date": trade_date.isoformat(),
        "symbol": symbol,
        "segment": cell("Segment") or None,
        "lots": lots,
        "total_value_lakhs": total_value,
        "avg_daily_turnover_lakhs": turnover,
        "premium_value_lakhs": premium_value,
    }
    if instrument == "OPTFUT":
        payload["row_class"] = "OPTIONS"
    return payload


def premium_field(header_map: dict[str, int]) -> bool:
    return "Premium Value (Lakhs)" in header_map


def turnover_field(header_map: dict[str, int]) -> bool:
    return "Avg Daily Turnover(Lakhs)" in header_map


def build_header_map(headers: list[str]) -> dict[str, int]:
    m: dict[str, int] = {}
    for i, h in enumerate(headers):
        key = re.sub(r"\s+", " ", h).strip()
        if key not in m:
            m[key] = i
    return m
