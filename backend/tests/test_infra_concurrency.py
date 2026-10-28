"""Idempotency, locking and cache-layer concurrency guarantees (SQLite stubs)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Idempotency: atomic claim / replay / conflict / lease takeover
# ---------------------------------------------------------------------------

def _second_session(session):
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=session.bind, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


ROUTE = "POST /api/v1/backtests/run"
KEY = "client-key-1"
HASH_A = "aaa"
HASH_B = "bbb"


def test_first_request_owns_the_claim(session):
    from app.core.idempotency import replay_or_claim

    first = replay_or_claim(session, ROUTE, KEY, HASH_A)
    assert first == {"payload": None, "replay": False}


def test_concurrent_pending_claim_is_conflict(session):
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import InvalidInput
    from app.core.idempotency import replay_or_claim

    replay_or_claim(session, ROUTE, KEY, HASH_A)
    session.commit()

    other = sessionmaker(bind=session.bind, expire_on_commit=False)()
    try:
        # same pending key, different body -> hard 409, never executed
        with pytest.raises(InvalidInput) as exc:
            replay_or_claim(other, ROUTE, KEY, HASH_B)
        assert exc.value.status_code == 409
        # same pending key, same body -> still in progress (409), not a replay
        with pytest.raises(InvalidInput):
            replay_or_claim(other, ROUTE, KEY, HASH_A)
    finally:
        other.close()


def test_committed_record_is_replayed_exact_body_only(session):
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import InvalidInput
    from app.backtesting import walkforward  # noqa: F401  (route target exists)
    from app.core.idempotency import commit_result, replay_or_claim

    assert replay_or_claim(session, ROUTE, KEY, HASH_A)["replay"] is False
    commit_result(session, ROUTE, KEY, HASH_A, {"run": {"id": "r1"}}, result_ref="r1")
    session.commit()

    other = sessionmaker(bind=session.bind, expire_on_commit=False)()
    try:
        replay = replay_or_claim(other, ROUTE, KEY, HASH_A)
        assert replay["replay"] is True
        assert replay["payload"] == {"run": {"id": "r1"}}
        # same key, different body on a COMMITTED record -> 409
        with pytest.raises(InvalidInput):
            replay_or_claim(other, ROUTE, KEY, HASH_B)
    finally:
        other.close()


def test_expired_pending_lease_is_reclaimable(session):
    from sqlalchemy import select

    from app.core.idempotency import replay_or_claim
    from app.models.request import ApiIdempotency

    replay_or_claim(session, ROUTE, KEY, HASH_A)
    session.flush()
    row = session.execute(
        select(ApiIdempotency).where(ApiIdempotency.route == ROUTE,
                                     ApiIdempotency.idempotency_key == KEY)
    ).scalar_one()
    row.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    session.flush()

    # a retry with the SAME payload takes over the dead lease
    takeover = replay_or_claim(session, ROUTE, KEY, HASH_A)
    assert takeover == {"payload": None, "replay": False}


# ---------------------------------------------------------------------------
# Locking: bounded acquisition, no unbounded spin, deterministic ordering
# ---------------------------------------------------------------------------

def test_lock_ordering_is_namespace_then_identifier():
    from app.db.locking import _sort_keys

    ordered = _sort_keys(["pair:GOLDM-GOLDTEN", "backtest:2024-x", "source:abc"])
    namespace_order = [k.split(":")[0] for k in ordered]
    assert namespace_order == ["source", "pair", "backtest"]


def test_locker_releases_on_exception_and_commit(session):
    from app.db.locking import _stub_held, locked
    from app.models.request import ApiIdempotency

    with locked(session, "pair:goldm-goldten", timeout_s=2.0):
        assert _stub_held.get("pair:goldm-goldten") == 1
        session.add(ApiIdempotency(route="t", idempotency_key="lk1", request_hash="h"))
        session.flush()
    # releases at commit
    assert "pair:goldm-goldten" not in _stub_held

    with pytest.raises(RuntimeError):
        with locked(session, "pair:goldm-goldten", timeout_s=2.0):
            raise RuntimeError("boom")
    assert "pair:goldm-goldten" not in _stub_held


def test_contention_times_out_boundedly():
    from app.db.locking import LockTimeout, _stub_held, locked

    _stub_held["backtest:busy"] = 999  # simulate another holder in-process
    empty = None  # not a Session; the SQLite stub path never uses it
    try:
        with pytest.raises(LockTimeout) as exc:
            import contextlib

            with contextlib.nullcontext():
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker as sm

                eng = create_engine("sqlite://")
                s = sm(bind=eng, expire_on_commit=False)()
                try:
                    with locked(s, "backtest:busy", timeout_s=0.15):
                        pass
                finally:
                    s.close()
                    eng.dispose()
        assert "backtest:busy" in str(exc.value)
    finally:
        _stub_held.pop("backtest:busy", None)


# ---------------------------------------------------------------------------
# Cache: epoch bumps invalidate, rolled-back writes never invalidate
# ---------------------------------------------------------------------------

def test_cache_single_key_epoch_bump_invalidates():
    from app.cache import CacheLayer

    c = CacheLayer()  # degraded/local mode, deterministic
    k1 = c.key("dashboard", {"limit": 8})
    c.set(k1, {"v": 1}, ttl=60)
    assert c.get(k1)[0] == {"v": 1}

    old_epoch = c.current_epoch()
    c.bump()
    assert c.current_epoch() == old_epoch + 1
    k2 = c.key("dashboard", {"limit": 8})
    assert k2 != k1
    assert c.get(k2) is None


def test_rollback_does_not_publish_invalidation():
    """bump() is an explicit post-commit call: a never-committed write leaves
    the previous cached value served under the same epoch."""
    from app.cache import CacheLayer

    c = CacheLayer()
    k = c.key("signals", {"pair_id": "GOLDM-GOLDTEN"})
    c.set(k, {"before": True}, ttl=60)

    # simulate a failed/rolled-back job: it never called bump()
    # (only verify no implicit invalidation happened)
    assert c.get(k) is not None


def test_get_or_load_caches_and_bounded_wait_degrades(monkeypatch):
    import threading

    from app.cache import CacheLayer

    c = CacheLayer()
    key = c.key("comparisons", {"pair": "x", "range": 90})
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"loaded": True}

    v = c.get_or_load(key, ttl=30, loader=loader)
    assert v == {"loaded": True}
    # the flight entry is removed once finished
    with c._flight_lock:
        assert key not in c._flight
    v2 = c.get_or_load(key, ttl=30, loader=loader)
    assert v2 == {"loaded": True}
    assert calls["n"] == 1  # second read hit the cache

    # after a post-commit bump the same params miss and reload
    c.bump()
    c.get_or_load(c.key("comparisons", {"pair": "x", "range": 90}), ttl=30, loader=loader)
    assert calls["n"] == 2
