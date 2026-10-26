"""Transaction-scoped advisory locking with a single global lock ordering.

Protocol (documented in docs/concurrency.md):
- Resources are addressed as namespace-qualified strings, e.g.
  ``source:<sha>``, ``dataset:<name>``, ``backtest:<idemkey>``.
- Every code path acquires all locks in the deterministic global order
  (namespace lexicographic, then identifier lexicographic) inside the growing
  phase; locks release together at commit/rollback (shrinking phase = commit).
  No path releases one lock and then acquires another.
- Locks are PostgreSQL transaction-scoped advisory locks
  (``pg_advisory_xact_lock``), so they auto-release at transaction end.
- On SQLite (tests), a bounded in-process re-entrant stub keeps the ordering
  contract testable without server-side sessions.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session

NAMESPACES = ("source", "dataset", "pair", "calibration", "backtest", "ingestion")

_local = threading.local()


class LockTimeout(Exception):
    """Raised when a bounded advisory-lock acquisition cannot complete."""


def lock_key(namespace: str, identifier: str) -> str:
    return f"{namespace.lower()}:{identifier.lower()}"


def _sort_keys(keys: list[str]) -> list[str]:
    """Ordering: namespace (NAMESPACES index), then identifier lexicographic."""
    def rank(k: str) -> tuple[int, str]:
        ns, _, ident = k.partition(":")
        order = NAMESPACES.index(ns) if ns in NAMESPACES else len(NAMESPACES)
        return order, ident

    return sorted(keys, key=rank)


# ---------------------------------------------------------------------------
# SQLite/test fallback: process-local, per-key, strictly ordered stub.

_stub_lock = threading.Lock()
_stub_held: dict[str, int] = {}
_local_stub = threading.local()


def _stub_acquire(keys: list[str], timeout_s: float) -> None:
    """Bounded acquisition: lock contention can never spin forever."""
    import time

    deadline = time.monotonic() + timeout_s
    held = getattr(_local_stub, "held", [])
    held_set = set(held)
    grow = _sort_keys([k for k in keys if k not in held_set])
    remaining = grow
    while remaining:
        with _stub_lock:
            free = [k for k in remaining if k not in _stub_held]
            for k in free:
                _stub_held[k] = _stub_held.get(k, 0) + 1
        if len(free) == len(remaining):
            break
        if time.monotonic() >= deadline:
            # Release anything already acquired this pass before failing.
            with _stub_lock:
                for k in free:
                    n = _stub_held.get(k, 0)
                    if n > 1:
                        _stub_held[k] = n - 1
                    else:
                        _stub_held.pop(k, None)
            raise LockTimeout(f"could not acquire lock(s) {remaining} within {timeout_s:.1f}s")
        time.sleep(0.005)
        remaining = _sort_keys([k for k in remaining if k not in _stub_held])
    new_held = list(held) + grow
    _local_stub.held = new_held


def _stub_release_all() -> None:
    held = getattr(_local_stub, "held", None)
    if not held:
        return
    with _stub_lock:
        for k in held:
            current = _stub_held.get(k, 0)
            if current > 1:
                _stub_held[k] = current - 1
            else:
                _stub_held.pop(k, None)
    _local_stub.held = []


# ---------------------------------------------------------------------------
# Main context manager


@contextmanager
def locked(
    session: Session, *resources: str, timeout_s: float | None = None
) -> Iterator[Session]:
    """Acquire the given transaction-scoped advisory locks, already ordered.

    Usage: a single call carries all locks the code path needs; the context
    manager performs the growing phase (all acquisitions strictly before any
    release) and releases the locks when the session's transaction commits or
    rolls back.
    """
    if not resources:
        yield session
        return
    ordered = _sort_keys([k if ":" in k else k for k in resources])
    if timeout_s is None:
        from app.core.config import get_settings

        timeout_s = get_settings().db_lock_timeout_ms / 1000.0
    is_sqlite = session.bind.dialect.name == "sqlite"
    if is_sqlite:
        # Fake a serialised ordering for tests; releases at commit/rollback
        # boundary in the same way semantics are honoured.
        _stub_acquire(ordered, timeout_s)
        try:
            yield session
            if session.in_transaction():
                session.commit()
            return
        except Exception:
            session.rollback()
            raise
        finally:
            _stub_release_all()
    import time

    deadline = time.monotonic() + timeout_s
    acquired = [k for k in ordered if k not in getattr(_local, "held_keys", frozenset())]
    try:
        for k in _sort_keys(acquired):
            digest = int.from_bytes(hashlib.blake2b(k.encode("utf-8"), digest_size=8).digest(), "big")
            while True:
                got = session.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": digest}
                ).scalar_one()
                if got:
                    break
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"could not acquire lock {k} within {timeout_s:.1f}s")
                time.sleep(0.02)
            held = getattr(_local, "held_keys", frozenset())
            _local.held_keys = held | {k}
    except LockTimeout:
        # All advisory locks are transaction-scoped: the surrounding rollback
        # releases every already-acquired lock. Nothing to unwind manually.
        raise
    try:
        yield session
    finally:
        # Shrinking phase: everything releases with the transaction end.
        for k in _sort_keys(acquired):
            held = getattr(_local, "held_keys", frozenset())
            _local.held_keys = held - {k}
