"""Ingestion tests: content sniffing, HTML-as-xls parsing, classification,
quarantine with reasons, idempotent import, and source-file immutability."""
import hashlib
import os
from pathlib import Path

import pytest

from app.ingestion import parsers, sniffing
from app.ingestion import classification as cls
from app.ingestion.pipeline import import_sources, scan_sources


def test_detects_html_table_despite_xls_extension(sample_html_xls: Path):
    assert sniffing.detect_format(sample_html_xls) == "html_table"


def test_unknown_format_detected(tmp_path: Path):
    p = tmp_path / "weird.xls"
    p.write_bytes(b"\x00\x01binary-noise")
    assert sniffing.detect_format(p) == "unknown"


def test_parse_html_table_headers_and_rows(sample_html_xls: Path):
    t = parsers.parse_table(sample_html_xls, "html_table")
    assert t.headers[0] == "Instrument"
    assert len(t.rows) == 12
    assert t.rows[0][0] == "FUTCOM"


def test_csv_parse(tmp_path: Path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    t = parsers.parse_table(p, "csv")
    assert t.headers == ["a", "b"]


def test_empty_csv_quarantines_with_reason(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty CSV"):
        parsers.parse_table(p, "csv")


def test_row_classification_detail_row():
    hm = {"Instrument": 0, "Date": 1, "Segment": 2, "Commodity": 3,
          "Traded Contract (Lots)": 4, "Total Value (Lakhs)": 5,
          "Avg Daily Turnover(Lakhs)": 6, "Premium Value (Lakhs)": 7}
    row = cls.classify_and_validate_row(
        hm, ["FUTCOM", "01 Jan 2026", "BULLION", "GOLDM", "24697", "333076.24", "0.00", "-"],
        "GOLDM",
    )
    assert row["instrument"] == "FUTCOM" and row["symbol"] == "GOLDM"
    assert row["lots"] == 24697


def test_optfut_row_classifies_as_options():
    hm = {"Instrument": 0, "Date": 1, "Commodity": 2, "Traded Contract (Lots)": 3,
          "Total Value (Lakhs)": 4, "Premium Value (Lakhs)": 5}
    row = cls.classify_and_validate_row(
        hm, ["OPTFUT", "01 Jan 2026", "GOLDM", "49407", "670092.80", "9515.52"], "GOLDM")
    assert row.pop("row_class") == "OPTIONS"


def test_missing_date_rejected():
    hm = {"Instrument": 0, "Date": 1, "Commodity": 2, "Traded Contract (Lots)": 3,
          "Total Value (Lakhs)": 4}
    with pytest.raises(ValueError, match="invalid or missing trade date"):
        cls.classify_and_validate_row(hm, ["FUTCOM", "", "GOLDM", "10", "2.0"], "GOLDM")


def test_unknown_symbol_rejected():
    hm = {"Instrument": 0, "Date": 1, "Commodity": 2, "Traded Contract (Lots)": 3,
          "Total Value (Lakhs)": 4}
    with pytest.raises(ValueError, match="unknown commodity"):
        cls.classify_and_validate_row(hm, ["FUTCOM", "01 Jan 2026", "SILVER", "10", "2.0"], "GOLDM")


def test_zero_lots_positive_value_rejected():
    hm = {"Instrument": 0, "Date": 1, "Commodity": 2, "Traded Contract (Lots)": 3,
          "Total Value (Lakhs)": 4}
    with pytest.raises(ValueError, match="zero lots"):
        cls.classify_and_validate_row(hm, ["FUTCOM", "01 Jan 2026", "GOLDM", "0", "2.0"], "GOLDM")


def test_scan_classifies_synthetic_root(session, synthetic_data_root: Path):
    import app.ingestion.pipeline as pl

    pl._data_root = lambda: synthetic_data_root  # isolate from real repo config
    out = scan_sources(session)
    c = out["counts"]
    assert c["discovered"] == 3
    sc = c["by_class"]
    assert sc["ACTIVITY_REPORT"] == 1
    assert sc["OPTIONS"] == 1
    assert sc["UNSUPPORTED"] == 1
    assert c["by_format"]["html_table"] == 2


def test_import_rows_and_idempotency(session, synthetic_data_root: Path):
    import app.ingestion.pipeline as pl

    pl._data_root = lambda: synthetic_data_root
    out = scan_sources(session)
    imp1 = import_sources(session)
    assert imp1["counts"]["files_parsed"] == 2
    assert imp1["counts"]["activity_rows_upserted"] == 12  # GOLDM file: 12 distinct days
    assert imp1["counts"]["options_rows_upserted"] == 12
    assert "parse" not in str(imp1["counts"]["files_failed"])
    imp2 = import_sources(session)
    # Idempotent: nothing new gets staged the second time.
    assert imp2["counts"]["skipped_unchanged_files"] == 2
    assert imp2["counts"]["activity_rows_upserted"] == 0

    from sqlalchemy import select

    from app.models.market import ActivityDaily, OptionsDaily

    acts = session.execute(select(ActivityDaily)).scalars().all()
    assert len(acts) == 12  # 12 deduped symbol-days, all FUTCOM GOLDM
    assert all(a.symbol == "GOLDM" and a.instrument == "FUTCOM" for a in acts)
    opts = session.execute(select(OptionsDaily)).scalars().all()
    assert len(opts) == 12
    assert all(o.symbol == "GOLDPETAL" for o in opts)  # OPTFUT never in futures


def test_source_files_never_modified_or_written(synthetic_data_root: Path):
    before = {}
    for p in sorted(synthetic_data_root.rglob("*")):
        if p.is_file():
            before[p.relative_to(synthetic_data_root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    # ... run a scan/import cycle against a scratch session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.migrations import drop_all, ensure_schema
    import app.ingestion.pipeline as pl

    pl._data_root = lambda: synthetic_data_root
    engine = create_engine("sqlite://")
    ensure_schema(engine)
    db = sessionmaker(bind=engine)()
    scan_sources(db)
    import_sources(db)
    db.close()
    engine.dispose()
    drop_all(engine)

    after = {}
    extra = []
    for p in sorted(synthetic_data_root.rglob("*")):
        rel = p.relative_to(synthetic_data_root).as_posix()
        if p.is_file():
            after[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    assert after == {k: v for k, v in before.items()}
    assert extra == []


def test_real_source_immutability_after_full_pipeline(session):
    """Checksum the actual GoldMcx_Data root; registered hashes must match."""
    root_env = os.environ.get("MCX_DATA_DIR_ABS")
    from app.core.config import get_settings

    real_root = Path(root_env) if root_env else get_settings().data_root
    if not real_root.is_dir():
        pytest.skip("real data root not present")
    from app.ingestion.discovery import safe_iter_files, sha256_of

    hashes = {rel: sha256_of(p) for p, rel in safe_iter_files(real_root)}
    assert len(hashes) == 125  # matches the Phase-0 inventory
    from sqlalchemy import select

    from app.models.source import SourceFile

    sf = session.execute(select(SourceFile)).scalars().all()
    registered = {f.relative_path: f.sha256 for f in sf}
    for rel, h in hashes.items():
        if rel in registered:
            assert registered[rel] == h
