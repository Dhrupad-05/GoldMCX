"""Shared pytest fixtures. Tests never touch the real GoldMcx_Data files except
for a checksum-only immutability test (read-only)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
for _p in (str(BACKEND_DIR), str(ROOT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite:///:memory:")


@pytest.fixture()
def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.migrations import ensure_schema

    engine = create_engine("sqlite://")
    ensure_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def seed_activity_rows(session, *, days: int = 28, year: int = 2024):
    """Seed activity rows for all four symbols over `days` January dates."""
    from datetime import date

    from app.analytics.normalize import seed_contract_specs
    from app.models.market import ActivityDaily

    seed_contract_specs(session)
    # (symbol, lots, value_per_lot rupees) - value_per_lot gives a stable
    # provisional price per lot for the day.
    scales = {
        "GOLDM": (1000, 131000.0),
        "GOLDTEN": (900, 139000.0),
        "GOLDGUINEA": (800, 67000.0),
        "GOLDPETAL": (700, 8400.0),
    }
    for i in range(1, days + 1):
        d = date(year, 1, min(i, 28))
        for symbol, (lots, vpl) in scales.items():
            session.add(ActivityDaily(
                symbol=symbol, trade_date=d, instrument="FUTCOM",
                report_type="detail", lots=lots + i,
                total_value_lakhs=(vpl * (lots + i)) / 100000.0,
                data_status="VERIFIED",
            ))
    session.commit()


@pytest.fixture()
def seeded_activity(session):
    seed_activity_rows(session)
    return session


@pytest.fixture()
def sample_html_xls(tmp_path: Path) -> Path:
    """Synthetic MCX-style HTML table saved with an .xls extension."""
    rows = []
    for i in range(1, 13):
        date_s = f"0{i} Jan 2024" if i < 10 else f"{i} Jan 2024"
        rows.append(
            f"<tr><td>FUTCOM</td><td>{date_s}</td><td>BULLION</td><td>GOLDM</td>"
            f"<td>{1000 + i}</td><td>1.21{(i % 10)}</td><td>0.00</td><td>-</td></tr>"
        )
    html = (
        "<html><body><table><thead><tr>"
        "<th>Instrument</th><th>Date</th><th>Segment</th><th>Commodity</th>"
        "<th>Traded Contract (Lots)</th><th>Total Value (Lakhs)</th>"
        "<th>Avg Daily Turnover(Lakhs)</th><th>Premium Value (Lakhs)</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>"
    )
    p = tmp_path / "DateWise 2024 Detail report.xls"
    p.write_text(html, encoding="utf-8")
    return p


@pytest.fixture()
def synthetic_data_root(tmp_path: Path, sample_html_xls: Path) -> Path:
    """A temp data root mimicking the real layout (options + spec + activity)."""
    root = tmp_path / "data_root"
    sub = root / "GOLDM"
    sub.mkdir(parents=True)
    (sub / "DateWise 2024 Detail report.xls").write_bytes(sample_html_xls.read_bytes())
    opt = root / "GOLDPETAL"
    opt.mkdir()
    # OPTFUT rows make this an OPTIONS-class report; commodity -> GOLDPETAL.
    opt_html = sample_html_xls.read_text(encoding="utf-8").replace(
        "<td>FUTCOM</td>", "<td>OPTFUT</td>").replace(
        "<td>GOLDM</td>", "<td>GOLDPETAL</td>")
    (opt / "DateWise 2024 Detail report.xls").write_text(opt_html, encoding="utf-8")
    (root / "notes.txt").write_bytes(b"\x00\x01binary-noise")
    return root


@pytest.fixture()
def client(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import app

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.migrations import ensure_schema

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    ensure_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c, factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def api_seeded(client, seeded_activity):
    """Client whose API database mirrors the seeded activity fixture."""
    c, factory = client
    db = factory()
    try:
        seed_activity_rows(db)
        from app.services.market_builder import rebuild_market_tables

        rebuild_market_tables(db)
        yield c, db
    finally:
        db.close()
