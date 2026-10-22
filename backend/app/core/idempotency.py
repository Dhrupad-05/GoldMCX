"""HTTP Idempotency-Key handling for mutating operations.

Contract (docs/concurrency.md):
- Client may send `Idempotency-Key`; missing key = no record (behaviour today).
- First execution commits a record with state=committed and the result body.
- Concurrent same-key request: if a committed record exists with the same
  request_hash, replay the stored response (200) without re-executing.
- Same key with a different payload: 409 conflict, never executed.
- Cancellation/rollback leaves no committed record: failures are not cached.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, InvalidInput
from app.models.request import ApiIdempotency


def request_fingerprint(body: dict | None) -> str:
    basis = json.dumps(body or {}, sort_keys=True, default=str)
    return hashlib.sha256(basis.encode()).hexdigest()


def idempotency_key_of(request: Request) -> str | None:
    raw = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    return raw.strip() if raw else None


def replay_or_claim(
    session: Session, route: str, idem_key: str, body_hash: str
) -> dict:
    """Return a replay payload when a matching committed record exists."""
    row = session.execute(
        select(ApiIdempotency).where(
            ApiIdempotency.route == route,
            ApiIdempotency.idempotency_key == idem_key,
        )
    ).scalar_one_or_none()
    if row is None:
        return {"payload": None, "replay": False}
    if row.request_hash != body_hash:
        raise InvalidInput(
            "Idempotency-Key already used with a different request body.",
            status_code=409,
        )
    if row.state == "committed":
        return {"payload": row.response_body, "replay": True}
    if row.state == "pending":
        raise InvalidInput("A request with this key is still in progress.", status_code=409)
    # failed record: expired, safe to retry with the same key
    return {"payload": row.response_body, "replay": False}


def commit_result(
    session: Session, route: str, idem_key: str, body_hash: str,
    response_body: dict, result_ref: str | None = None,
) -> None:
    """Persist a committed idempotency record atomically with the response."""
    existing = session.execute(
        select(ApiIdempotency).where(
            ApiIdempotency.route == route,
            ApiIdempotency.idempotency_key == idem_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_hash != body_hash:
            raise InvalidInput(
                "Idempotency-Key reused for a different payload.", status_code=409
            )
        existing.state = "committed"
        existing.response_body = response_body
        existing.result_ref = result_ref
        session.flush()
        return
    session.add(ApiIdempotency(
        route=route, idempotency_key=idem_key, request_hash=body_hash,
        state="committed", response_body=response_body, result_ref=result_ref,
        created_at=datetime.now(timezone.utc),
    ))
    session.flush()


def idempotency_conflict(message: str) -> InvalidInput:
    return InvalidInput(message, status_code=409)
