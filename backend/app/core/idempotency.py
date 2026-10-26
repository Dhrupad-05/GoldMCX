"""HTTP Idempotency-Key handling for mutating operations.

Contract (docs/concurrency.md):
- Client may send `Idempotency-Key`; missing key = no record (behaviour today).
- The FIRST request atomically CLAIMS the key (INSERT of a state=pending row
  protected by uq_idempotency_route_key) before its work starts, so two
  concurrent first requests can never both execute.
- A concurrent same-key request: if a committed record exists with the same
  request_hash, replay the stored response (without re-executing).
- Same key with a different payload: 409 conflict, never executed.
- Failed/executions leave a pending record with a bounded lease; stale
  leases (crashed/cancelled request) are automatically reclaimable, so a key
  is never wedged in 409-forever.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, InvalidInput
from app.models.request import ApiIdempotency

# A pending claim younger than this is another live in-flight request; older
# claims are dead leases a retry may take over.
PENDING_LEASE_SECONDS = 600


def request_fingerprint(body: dict | None) -> str:
    basis = json.dumps(body or {}, sort_keys=True, default=str)
    return hashlib.sha256(basis.encode()).hexdigest()


def idempotency_key_of(request: Request) -> str | None:
    raw = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    return raw.strip() if raw else None


def replay_or_claim(
    session: Session, route: str, idem_key: str, body_hash: str
) -> dict:
    """Atomically claim the key, then return a replay payload when one exists.

    The INSERT ... unique-constraint-protected claim happens BEFORE any work;
    a lost insert race falls back to reading the winning row inside a savepoint
    so the surrounding transaction is not aborted.
    """
    claim = ApiIdempotency(
        route=route, idempotency_key=idem_key, request_hash=body_hash,
        state="pending", created_at=datetime.now(timezone.utc),
    )
    try:
        with session.begin_nested():
            session.add(claim)
            session.flush()
        return {"payload": None, "replay": False}  # we own the claim
    except IntegrityError:
        pass  # someone else already holds a record for this key
    row = session.execute(
        select(ApiIdempotency).where(
            ApiIdempotency.route == route,
            ApiIdempotency.idempotency_key == idem_key,
        )
    ).scalar_one_or_none()
    if row is None:  # vanished between conflict and read: claim vanished
        return {"payload": None, "replay": False}
    if row.state == "committed":
        if row.request_hash != body_hash:
            raise InvalidInput(
                "Idempotency-Key already used with a different request body.",
                status_code=409,
            )
        return {"payload": row.response_body, "replay": True}
    # state == pending (or expired-lease takeover below)
    if row.request_hash != body_hash:
        raise InvalidInput(
            "Idempotency-Key already in use with a different request body.",
            status_code=409,
        )
    lease_expired = _row_older_than(row, PENDING_LEASE_SECONDS)
    if not lease_expired:
        raise InvalidInput(
            "A request with this key is still in progress.", status_code=409
        )
    # Dead lease: reclaim it under the same key (same payload, again valid).
    row.state = "pending"
    row.request_hash = body_hash
    row.created_at = datetime.now(timezone.utc)
    session.flush()
    return {"payload": None, "replay": False}


def _row_older_than(row: ApiIdempotency, seconds: int) -> bool:
    created = row.created_at
    if created is None:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created >= timedelta(seconds=seconds)


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
