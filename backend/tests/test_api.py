"""API tests: schemas, validation errors, health/readiness, ingestion flow."""
from datetime import date

import pytest
from sqlalchemy import select


def test_health_live(client):
    c, _ = client
    r = c.get("/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "alive"


def test_health_ready(client):
    c, _ = client
    r = c.get("/health/ready")
    assert r.status_code == 200
    assert "database" in r.json()


def test_contracts_empty_db(client):
    c, factory = client
    r = c.get("/api/v1/contracts")
    assert r.status_code == 200
    assert all(x["status"] == "NO_DATA" for x in r.json()["contracts"])


def test_error_schema_is_consistent(client):
    c, _ = client
    r = c.get("/api/v1/contracts/BOGUS")
    assert r.status_code == 404
    body = r.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "not_found"


def test_comparison_requires_pair(client):
    c, _ = client
    r = c.get("/api/v1/comparisons")
    assert r.status_code == 400


def test_comparison_rejects_unknown_and_same_symbols(client):
    c, _ = client
    assert c.get("/api/v1/comparisons", params={"left": "GOLDM", "right": "SILVER"}).status_code == 404
    assert c.get("/api/v1/comparisons", params={"left": "GOLDM", "right": "GOLDM"}).status_code == 400
    assert c.get("/api/v1/comparisons", params={"left": "GOLDM", "right": "GOLD"}).status_code == 404


def test_comparison_rejects_same_symbol(client):
    c, _ = client
    r = c.get("/api/v1/comparisons", params={"left": "GOLDM", "right": "GOLDM"})
    assert r.status_code == 400


def test_comparison_alias_and_canonical_equivalence(api_seeded):
    c, _ = api_seeded
    r1 = c.get("/api/v1/comparisons", params={"pair": "REST-GOLDPETAL"})
    r2 = c.get("/api/v1/comparisons", params={"pair": "GOLDGUINEA-GOLDPETAL"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["pair_id"] == r2.json()["pair_id"] == "GOLDGUINEA-GOLDPETAL"
    points = r1.json()["points"]
    assert len(points) == 28  # all 28 shared fixture dates
    assert points[0]["source_status"] == "PROVISIONAL"


def test_comparison_series_range_filter(api_seeded):
    # range_days anchors on the clock today; the seeded fixture lives in Jan
    # 2024, so a 30-day lookback legitimately has no rows. Anchor the window
    # explicitly instead, and assert the SQL filter narrows the result.
    c, _ = api_seeded
    full = c.get("/api/v1/comparisons", params={"pair": "GOLDM-GOLDPETAL"})
    assert full.status_code == 200
    ranged = c.get(
        "/api/v1/comparisons",
        params={"pair": "GOLDM-GOLDPETAL", "start": "2024-01-05", "end": "2024-01-15"},
    )
    assert ranged.status_code == 200
    all_dates = [p["trade_date"] for p in full.json()["points"]]
    ranged_dates = [p["trade_date"] for p in ranged.json()["points"]]
    assert 0 < len(ranged_dates) < len(all_dates)
    assert all("2024-01-05" <= d <= "2024-01-15" for d in ranged_dates)


def test_contract_series_endpoint(api_seeded):
    c, _ = api_seeded
    r = c.get("/api/v1/contracts/GOLDM/series")
    assert r.status_code == 200
    body = r.json()
    assert body["derivation_method"] == "activity_implied_value_per_lot"
    assert body["data_status"] == "PROVISIONAL"
    assert len(body["points"]) >= 20


def test_model_calibrate_and_score_flow(api_seeded):
    c, _ = api_seeded
    r = c.post("/api/v1/model/pairs/GOLDM-GOLDPETAL/calibrate",
               json={"train_end": "2024-01-20"})
    assert r.status_code == 200
    cal = r.json()
    assert cal["scale_method"] in ("mad", "iqr", "floor")
    # Held-out scoring date after train_end:
    r2 = c.post("/api/v1/model/pairs/GOLDM-GOLDPETAL/score",
                json={"observation_date": "2024-01-27"})
    assert r2.status_code == 200
    body = r2.json()
    for key in ("pair_id", "robust_z", "anomaly_score", "is_anomaly",
                "explanation", "calibration", "warnings", "algorithm"):
        assert key in body
    # Scoring a training date must be rejected (calibration isolation):
    r3 = c.post("/api/v1/model/pairs/GOLDM-GOLDPETAL/score",
                json={"observation_date": "2024-01-05"})
    assert r3.status_code == 400
    # Legacy alias maps to the canonical pair; the auto-calibration holds out
    # the last feature date (train_end), which is scorable:
    r4 = c.post("/api/v1/model/pairs/REST-GOLDPETAL/score",
                json={"observation_date": "2024-01-28"})
    assert r4.status_code == 200
    assert r4.json()["pair_id"] == "GOLDGUINEA-GOLDPETAL"


def test_signals_empty_then_populated(client):
    c, _ = client
    r = c.get("/api/v1/signals")
    assert r.status_code == 200 and r.json() == []


def test_signals_populated_after_model_run(api_seeded):
    c, _ = api_seeded
    c.post("/api/v1/model/pairs/GOLDM-GOLDPETAL/calibrate", json={"train_end": "2024-01-20"})
    c.post("/api/v1/model/pairs/GOLDM-GOLDPETAL/score", json={"observation_date": "2024-01-27"})
    r2 = c.get("/api/v1/signals")
    body = r2.json()
    assert len(body) >= 1
    sig = body[0]
    assert sig["disposition"] in ("ACTIONABLE", "WATCH", "IGNORE", "UNSCORABLE")
    assert sig["status"] in ("ANOMALOUS", "NORMAL", "UNSCORABLE")
    assert "expiry_unassessable" in sig["reason_codes"] or len(sig["reason_codes"]) > 0


def test_ingestion_quality_report_requires_scan(client):
    c, _ = client
    r = c.get("/api/v1/ingestion/quality-report")
    assert r.status_code == 404


def test_unknown_signal_404(client):
    c, _ = client
    r = c.get("/api/v1/signals/999999")
    assert r.status_code == 404


def test_dashboard_summary_note(api_seeded):
    c, _ = api_seeded
    r = c.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["data_status"] == "PROVISIONAL"
    assert body["source_quality"]["nivel"] == "activity_reports_only"
