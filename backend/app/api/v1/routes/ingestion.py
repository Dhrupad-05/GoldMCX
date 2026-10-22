"""Ingestion endpoints (local/admin context; never write into the source root)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.core.idempotency import (
    commit_result,
    idempotency_key_of,
    replay_or_claim,
)
from app.db.locking import locked
from app.db.session import get_session
from app.ingestion import pipeline
from app.models.source import IngestionRun, RawSourceRow, SourceFile

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# Local/admin guard: ingestion mutates backend data and reads the configured
# filesystem root, so it is only served to explicit admin requests (header) or
# in the development environment.
ADMIN_TOKEN_HEADER = "x-admin-token"


def _ensure_admin(request: Request) -> None:
    if request.headers.get(ADMIN_TOKEN_HEADER):
        return  # explicit admin context
    from app.core.config import get_settings

    s = get_settings()
    if s.app_env == "development":
        return  # localhost development automation is permitted
    from app.core.errors import InvalidInput

    raise InvalidInput(
        "Ingestion is admin-only outside development; send the 'x-admin-token' header.",
        status_code=403,
    )


@router.post("/scan")
def scan(request: Request, session: Session = Depends(get_session)):
    _ensure_admin(request)
    idem_key = idempotency_key_of(request)
    route = "POST /api/v1/ingestion/scan"
    if idem_key:
        replay = replay_or_claim(session, route, idem_key, request_hash_scan(request))
        if replay["payload"] is not None:
            return replay["payload"]
    with locked(session, "ingestion:scan"):
        out = pipeline.scan_sources(session)
    if idem_key:
        commit_result(session, route, idem_key, request_hash_scan(request), out, result_ref=out.get("run_id"))
        session.commit()
    return out


def request_hash_scan(request: Request) -> str:
    import hashlib

    return hashlib.sha256(str(request.query_params).encode()).hexdigest()


@router.post("/import")
def import_sources(request: Request, session: Session = Depends(get_session)):
    _ensure_admin(request)
    idem_key = idempotency_key_of(request)
    route = "POST /api/v1/ingestion/import"
    body_hash = request_hash_scan(request)
    if idem_key:
        replay = replay_or_claim(session, route, idem_key, body_hash)
        if replay["payload"] is not None:
            return replay["payload"]
    with locked(session, "ingestion:import", "ingestion:derived"):
        out = pipeline.import_sources(session)
    if idem_key:
        commit_result(session, route, idem_key, body_hash, out, result_ref=out.get("run_id"))
        session.commit()
    return out


@router.get("/runs/{run_id}")
def run_status(run_id: str, session: Session = Depends(get_session)):
    run = session.get(IngestionRun, run_id)
    if run is None:
        raise NotFound(f"Ingestion run '{run_id}' not found.")
    return {
        "run_id": run.id,
        "mode": run.mode,
        "parser_version": run.parser_version,
        "overall_status": run.overall_status,
        "counts": run.counts or {},
        "errors": run.errors or [],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/quality-report")
def quality_report(session: Session = Depends(get_session)):
    files = session.execute(select(SourceFile)).scalars().all()
    if not files:
        raise NotFound("No ingestion results yet. Run POST /ingestion/scan first.")
    by_class: dict[str, int] = {}
    by_format: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for f in files:
        by_class[f.source_class] = by_class.get(f.source_class, 0) + 1
        by_format[f.detected_format] = by_format.get(f.detected_format, 0) + 1
        statuses[f.validation_status] = statuses.get(f.validation_status, 0) + 1
    runs = session.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
    ).scalars().first()
    invalid_rows = session.execute(
        select(RawSourceRow).where(RawSourceRow.validation_status == "rejected").limit(50)
    ).scalars().all()
    reasons: dict[str, int] = {}
    for r in invalid_rows:
        for err in (r.errors or []):
            reasons[err] = reasons.get(err, 0) + 1
    return {
        "run_id": runs.id if runs else None,
        "overall_status": (runs.overall_status if runs else "no_runs"),
        "counts": runs.counts if runs else {},
        "by_class": by_class,
        "by_format": by_format,
        "source_status_totals": statuses,
        "rejection_reasons": reasons,
        "date_ranges": {},
        "by_symbol": {},
    }
