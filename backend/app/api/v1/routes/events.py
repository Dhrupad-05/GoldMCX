"""Events: dated observations of record. Only source-verifiable entries are
included; nothing here is fabricated market commentary.
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.normalize import VERIFIED_SPECS
from app.core.errors import NotFound
from app.db.session import get_session

router = APIRouter(prefix="/events", tags=["events"])


def _events() -> list[dict]:
    """Spec-version change events derived from the verified contract documents."""
    seen: dict[str, dict] = {}
    for spec in VERIFIED_SPECS:
        key = (spec["symbol"], spec["valid_from"].isoformat())
        seen.setdefault(key, {
            "id": f"SPEC-{spec['symbol']}-{spec['valid_from'].isoformat()}",
            "date": spec["valid_from"].isoformat(),
            "pair_id": None,
            "category": "contract_specification",
            "severity": "Moderate",
            "title": f"{spec['symbol']} specification effective from {spec['valid_from'].isoformat()}",
            "description": spec["notes"] or "",
            "source_document": spec["source_document_id"],
            "data_status": "VERIFIED",
        })
    return sorted(seen.values(), key=lambda e: e["date"], reverse=True)


@router.get("")
def list_events(
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    session: Session = Depends(get_session),
):
    items = _events()
    if category:
        items = [e for e in items if e["category"] == category]
    if date_from:
        items = [e for e in items if e["date"] >= date_from.isoformat()]
    if date_to:
        items = [e for e in items if e["date"] <= date_to.isoformat()]
    return {"events": items, "count": len(items)}
