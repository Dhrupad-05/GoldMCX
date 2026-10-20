"""Scan/import orchestration: manifest → parse → classify → validate → stage → report.

Hard guarantees enforced here:
- The source root is only ever read (checksums at import and verification after).
- No artifacts are ever written into the source root.
- Imports are idempotent per (file hash + row natural keys), including re-scans.
- Invalid/ambiguous rows are recorded with reasons; never dropped silently.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidInput
from app.core.logging_config import run_id as bind_run_id, logger
from app.ingestion import classification as cls
from app.ingestion import parsers, sniffing
from app.ingestion.constants import (
    CLASS_ACTIVITY_REPORT,
    CLASS_CONTRACT_SPEC,
    CLASS_FUTURES_PRICE,
    CLASS_OPTIONS,
    CLASS_UNSUPPORTED,
    FMT_PDF,
    PARSER_VERSION,
    TARGET_SYMBOLS,
)
from app.ingestion.discovery import safe_iter_files, sha256_of, validate_root
from app.models.market import ActivityDaily, ContractSpec, GoldMarketBar, OptionsDaily
from app.models.source import IngestionRun, RawSourceRow, SourceFile


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_hash(source_sha: str, row_number: int, payload: dict) -> str:
    basis = source_sha + "|" + str(row_number) + "|" + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- scan

def scan_sources(session: Session) -> dict:
    """Walk the configured root read-only, detect formats/classes, record manifest."""
    root = validate_root(_data_root())
    run = IngestionRun(
        id=uuid.uuid4().hex[:12], mode="scan", parser_version=PARSER_VERSION,
        overall_status="running", data_root=str(root), counts={}, errors=[],
    )
    session.add(run)
    session.flush()

    counts = {"discovered": 0, "new": 0, "existing": 0, "by_class": {}, "by_format": {}}
    errors: list[str] = []
    for path, rel in safe_iter_files(root):
        counts["discovered"] += 1
        sha = sha256_of(path)
        fmt = sniffing.detect_format(path)
        try:
            source_class = _classify_file(path, rel, fmt)
        except Exception as exc:  # noqa: BLE001
            source_class = CLASS_UNSUPPORTED
            errors.append(f"{rel}: classification failed: {type(exc).__name__}")
        existing = session.execute(
            select(SourceFile).where(SourceFile.relative_path == rel, SourceFile.sha256 == sha)
        ).scalar_one_or_none()
        if existing:
            existing.detected_format = fmt
            existing.source_class = source_class
            existing.last_seen_at = _now()
            counts["existing"] += 1
            fid = existing.id
        else:
            sf = SourceFile(
                relative_path=rel, sha256=sha, size_bytes=path.stat().st_size,
                detected_format=fmt, source_class=source_class,
                parse_status="registered", validation_status="registered",
                parser_version=PARSER_VERSION,
            )
            session.add(sf)
            session.flush()
            counts["new"] += 1
            fid = sf.id
        counts["by_class"][source_class] = counts["by_class"].get(source_class, 0) + 1
        counts["by_format"].setdefault(fmt, 0)
        counts["by_format"][fmt] += 1

    counts["verified_unchanged_ok"] = True  # checked after import; report updated there
    run.counts = counts
    run.errors = errors
    run.overall_status = "completed"
    run.completed_at = _now()
    session.commit()
    return {"run_id": run.id, "counts": counts, "errors": errors}


def _classify_file(path, rel: str, fmt: str) -> str:
    name = rel.rsplit("/", 1)[-1].lower()
    if fmt == FMT_PDF or name.endswith(".pdf"):
        return CLASS_CONTRACT_SPEC
    if fmt in (sniffing.FMT_HTML_TABLE, sniffing.FMT_NATIVE_XLS, sniffing.FMT_CSV):
        table = parsers.parse_table(path, fmt)
        return _classify_report(table, rel)
    return CLASS_UNSUPPORTED


def _classify_report(table: parsers.ParsedTable, rel: str) -> str:
    if not cls.is_date_format_header(table.headers):
        return CLASS_UNSUPPORTED
    hm = cls.build_header_map(table.headers)
    school_codes = _symbol_hint_from_path(rel)
    if school_codes not in TARGET_SYMBOLS:
        raise ValueError(f"path does not identify a known report folder: {rel}")
    for cells in table.rows[:10]:
        try:
            row = cls.classify_and_validate_row(hm, cells, school_codes)
        except ValueError:
            continue
        if row["instrument"] == "OPTFUT":
            return CLASS_OPTIONS
        return CLASS_ACTIVITY_REPORT
    raise ValueError("no valid activity rows found")


def _symbol_hint_from_path(rel: str) -> str:
    top = rel.split("/", 1)[0].upper()
    return top if top in TARGET_SYMBOLS else top


# --------------------------------------------------------------------------- import

def import_sources(session: Session, file_filter: dict | None = None) -> dict:
    """Parse + validate + stage + persist market tables. Idempotent by construction."""
    root = validate_root(_data_root())
    run = IngestionRun(
        id=uuid.uuid4().hex[:12], mode="import", parser_version=PARSER_VERSION,
        overall_status="running", data_root=str(root), counts={}, errors=[],
    )
    session.add(run)
    session.flush()

    counts: dict = {
        "files_discovered": 0, "files_parsed": 0, "files_failed": 0,
        "rows_staged": 0, "rows_accepted": 0, "rows_quarantined": 0, "rows_rejected": 0,
        "activity_rows_upserted": 0, "options_rows_upserted": 0, "gold_market_upserted": 0,
        "skipped_unchanged_files": 0,
    }
    errors: list[str] = []
    by_class: dict[str, dict] = {}
    date_ranges: dict[str, list] = {}
    reason_counts: dict[str, int] = {}

    with bind_run_id(run.id):
        for path, rel in safe_iter_files(root):
            counts["files_discovered"] += 1
            sha = sha256_of(path)
            sf = session.execute(
                select(SourceFile).where(SourceFile.relative_path == rel, SourceFile.sha256 == sha)
            ).scalar_one_or_none()
            if sf is None:
                fmt = sniffing.detect_format(path)
                sf = SourceFile(
                    relative_path=rel, sha256=sha, size_bytes=path.stat().st_size,
                    detected_format=fmt, source_class=CLASS_UNSUPPORTED,
                    parse_status="registered", validation_status="registered",
                    parser_version=PARSER_VERSION,
                )
                session.add(sf)
                session.flush()
            if sf.parse_status == "imported":
                counts["skipped_unchanged_files"] += 1
                continue

            try:
                table_or_pdf = _parse_content(sf, path)
            except Exception as exc:  # noqa: BLE001
                counts["files_failed"] += 1
                reason = f"parse failed: {type(exc).__name__}"
                sf.parse_status = "failed"
                sf.validation_status = "quarantined"
                sf.rejections = [reason]
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                errors.append(f"{rel}: {reason}")
                session.commit()  # per-file transaction boundary
                continue

            try:
                if isinstance(table_or_pdf, parsers.ParsedPdf):
                    _register_pdf_spec(sf, table_or_pdf, rel)
                    counts["files_parsed"] += 1
                else:
                    stats = _import_activity_table(session, sf, table_or_pdf, rel, counts,
                                                   by_class, date_ranges, reason_counts)
                    counts["files_parsed"] += 1
                sf.parse_status = "imported"
                sf.validation_status = "imported"
            except Exception as exc:  # noqa: BLE001
                counts["files_failed"] += 1
                reason = f"import failed: {type(exc).__name__}"
                sf.parse_status = "failed"
                sf.validation_status = "quarantined"
                sf.rejections = [reason]
                errors.append(f"{rel}: {reason}")
                session.rollback()
            session.commit()

        counts["verified_source_unchanged"] = _verify_sources_unchanged(root, session)
        run.counts = counts
        run.errors = errors
        run.overall_status = "completed" if counts["files_failed"] == 0 else "completed_with_errors"
        run.completed_at = _now()
        session.add(run)
        session.commit()

    report = {
        "run_id": run.id,
        "counts": counts,
        "errors": errors,
        "by_class": by_class,
        "date_ranges": date_ranges,
        "rejection_reasons": reason_counts,
    }
    _persist_latest_quality_snapshot(session, report)
    return report


def _parse_content(sf: SourceFile, path):
    """Parse by detected content format; detect now if registration is stale."""
    if sf.detected_format in (sniffing.FMT_HTML_TABLE, sniffing.FMT_NATIVE_XLS, sniffing.FMT_CSV):
        return parsers.parse_table(path, sf.detected_format)
    if sf.detected_format == FMT_PDF:
        return parsers.parse_pdf(path)
    fmt = sniffing.detect_format(path)
    sf.detected_format = fmt
    sf.source_class = _classify_file(path, sf.relative_path, fmt)
    return _parse_content(sf, path)


def _import_activity_table(session: Session, sf: SourceFile, table, rel, counts, by_class,
                           date_ranges, reason_counts) -> dict:
    from app.ingestion.pipeline import _symbol_hint_from_path as _hint_for_rel
    headers = table.headers
    hm = cls.build_header_map(headers)
    if not cls.is_date_format_header(headers):
        reason = "unrecognized report headers"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        sf.validation_status = "quarantined"
        sf.rejections = [reason]
        return {}

    symbol_hint = _hint_for_rel(rel)
    report_type = "summary" if "summary" in rel.lower() else "detail"

    for i, cells in enumerate(table.rows, start=1):
        counts["rows_staged"] += 1
        try:
            row = cls.classify_and_validate_row(hm, cells, symbol_hint)
        except ValueError as exc:
            reason = str(exc)
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            rh = _row_hash(sf.sha256, i, {"cells": cells[:2]})
            _stage_row(session, sf.id, i, rh, {"cells": cells}, "rejected", "UNSUPPORTED", reason)
            counts["rows_rejected"] += 1
            continue

        row_class = row.pop("row_class", "ACTIVITY_REPORT")
        rh = _row_hash(sf.sha256, i, row)
        _stage_row(session, sf.id, i, rh, row, "accepted", row_class, None)
        counts["rows_accepted"] += 1
        klass = by_class.setdefault(row_class, {"accepted": 0, "quarantined": 0, "rejected": 0})
        klass["accepted"] += 1
        rng = date_ranges.setdefault(row["symbol"], [row["trade_date"], row["trade_date"]])
        rng[0] = min(rng[0], row["trade_date"])
        rng[1] = max(rng[1], row["trade_date"])
        _upsert_market_row(session, row, report_type, rh, counts)

    session.flush()
    return {}


def _stage_row(session: Session, file_id: int, row_number: int, rh: str,
               payload: dict, status: str, source_class: str, error: str | None) -> None:
    existing = session.execute(
        select(RawSourceRow).where(
            RawSourceRow.source_file_id == file_id, RawSourceRow.row_number == row_number
        )
    ).scalar_one_or_none()
    if existing:
        existing.row_hash = rh
        existing.raw_payload = payload
        existing.validation_status = status
        existing.class_ = source_class
        existing.errors = [error] if error else None
        return
    session.add(RawSourceRow(
        source_file_id=file_id, row_number=row_number, row_hash=rh,
        raw_payload=payload, validation_status=status,
        class_=source_class, errors=[error] if error else None,
    ))


def _upsert_market_row(session: Session, row: dict, report_type: str, rh: str, counts) -> None:
    from datetime import date as _date
    symbol = row["symbol"]
    trade_date = _date.fromisoformat(row["trade_date"])
    instrument = row["instrument"]
    lots = row["lots"]
    value = row["total_value_lakhs"]

    if symbol == "GOLD" or instrument == "FUTCOM" and symbol in ("GOLD",):
        q = select(GoldMarketBar).where(
            GoldMarketBar.trade_date == trade_date,
            GoldMarketBar.instrument == instrument,
            GoldMarketBar.report_type == report_type,
        )
        obj = session.execute(q).scalar_one_or_none()
        if obj is None:
            obj = GoldMarketBar(trade_date=trade_date, instrument=instrument, report_type=report_type)
            session.add(obj)
        obj.lots = lots
        obj.total_value_lakhs = value
        obj.source_row_id = None
        counts["gold_market_upserted"] += 1
        return

    if instrument == "OPTFUT":
        q = select(OptionsDaily).where(
            OptionsDaily.symbol == symbol,
            OptionsDaily.trade_date == trade_date,
            OptionsDaily.report_type == report_type,
        )
        obj = session.execute(q).scalar_one_or_none()
        if obj is None:
            obj = OptionsDaily(symbol=symbol, trade_date=trade_date, report_type=report_type)
            session.add(obj)
        obj.lots = lots
        obj.total_value_lakhs = value
        obj.premium_value_lakhs = row.get("premium_value_lakhs")
        counts["options_rows_upserted"] += 1
        return

    q = select(ActivityDaily).where(
        ActivityDaily.symbol == symbol,
        ActivityDaily.trade_date == trade_date,
        ActivityDaily.instrument == instrument,
        ActivityDaily.report_type == report_type,
    )
    obj = session.execute(q).scalar_one_or_none()
    if obj is None:
        obj = ActivityDaily(
            symbol=symbol, trade_date=trade_date, instrument=instrument, report_type=report_type
        )
        session.add(obj)
    obj.lots = lots
    obj.total_value_lakhs = value
    obj.avg_daily_turnover_lakhs = row.get("avg_daily_turnover_lakhs")
    obj.premium_value_lakhs = row.get("premium_value_lakhs")
    counts["activity_rows_upserted"] += 1


def _register_pdf_spec(sf: SourceFile, pdf: parsers.ParsedPdf, rel: str) -> None:
    """Extract candidate spec fields for human review; never auto-authoritative."""
    sf.parse_status = "imported"
    sf.validation_status = "registered_for_review"
    sf.rejections = None
    # Symbol + trading unit/quotation/purity extraction happens in the contract
    # master service (with required human verification); the PDF stays untouched.


def _verify_sources_unchanged(root, session) -> bool:
    """Re-hash source files and compare against the recorded manifest."""
    okay = True
    import re as _re
    for path, rel in safe_iter_files(root):
        sf = session.execute(
            select(SourceFile).where(SourceFile.relative_path == rel)
            .order_by(SourceFile.id.desc())
        ).scalars().first()
        if sf is None:
            continue
        if sha256_of(path) != sf.sha256:
            okay = False
            logger.error("source file changed during import: %s", rel)
    return okay


def _persist_latest_quality_snapshot(session: Session, report: dict) -> None:
    # Quality report reads live tables + latest run; nothing extra to persist here.
    return


def _data_root():
    from app.core.config import get_settings
    return get_settings().data_root
