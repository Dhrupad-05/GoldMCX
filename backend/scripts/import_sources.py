"""CLI: python scripts/import_sources.py [--reset]

Runs scan → import → market rebuild against the configured source root and
prints the ingestion report. Default is idempotent; --reset drops backend
tables first (backend-owned DB only, never the source files).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_engine, get_session  # noqa: E402
from app.db.migrations import drop_all, ensure_schema  # noqa: E402
from app.ingestion import pipeline  # noqa: E402
from app.services.market_builder import rebuild_market_tables  # noqa: E402
from app.core.logging_config import setup_logging  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main(reset: bool = False) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    engine = get_engine()
    if reset:
        drop_all(engine)
    created = ensure_schema(engine)
    if created:
        print("created tables:", ", ".join(created))
    session = next(get_session())
    try:
        scan = pipeline.scan_sources(session)
        print("SCAN", scan["run_id"], scan["counts"])
        imp = pipeline.import_sources(session)
        print("IMPORT", imp["run_id"], imp["counts"])
        if imp["errors"]:
            print("errors:", imp["errors"][:10])
        built = rebuild_market_tables(session)
        print("MARKET_BUILDER", built["specs_added"], built["normalized_added"], built["pairs"])
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main("--reset" in sys.argv))
