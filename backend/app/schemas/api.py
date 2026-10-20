"""Pydantic API schemas (response/request DTOs)."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    error: dict = Field(..., example={"code": "invalid_input", "message": "..."})


class Health(BaseModel):
    status: str
    app_env: str
    version: str = "1.0.0"
    detail: str | None = None


class ContractSpecOut(BaseModel):
    symbol: str
    valid_from: date
    valid_to: date | None
    trading_unit_grams: float
    quote_grams: float
    purity_per_mille: int
    quote_rule: str
    verification_status: str
    source_document_id: str
    notes: str | None = None


class ContractOut(BaseModel):
    symbol: str
    display_name: str
    specs: list[ContractSpecOut]
    data_summary: dict


class NormalizedPricePoint(BaseModel):
    trade_date: date
    normalized_value: float
    source_status: str
    derivation_method: str


class SeriesResponse(BaseModel):
    symbol: str
    derivation_method: str
    data_status: str
    points: list[NormalizedPricePoint]
    spec_versions_applied: list[str] = []


class ComparisonPoint(BaseModel):
    trade_date: date
    spread_pct: float
    spread_change_pct: float | None = None
    price_ratio: float | None = None
    left_value_lakhs: float | None = None
    right_value_lakhs: float | None = None
    source_status: str = "PROVISIONAL"


class ComparisonResponse(BaseModel):
    pair_id: str
    left: str
    right: str
    range_start: date
    range_end: date
    derivation_method: str
    data_status: str
    point_count: int
    points: list[ComparisonPoint]


class SignalOut(BaseModel):
    id: int
    score_id: int
    pair_id: str
    observation_date: date
    status: str
    disposition: str
    severity: str
    robust_z: float
    score: float
    liquidity_status: str
    expiry_status: str
    cost_status: str
    reason_codes: list[str] = []
    data_status: str


class SignalDetail(SignalOut):
    observed_value: float
    explanation: str
    warnings: list[str] = []
    feature_values: dict = {}
    checks: list[dict] = []
    calibration: dict = {}
    not_a_trade_warning: str = (
        "Anomaly scores are screening heuristics, not probabilities of profit. "
        "This is not investment advice."
    )


class CalibrationOut(BaseModel):
    id: int
    pair_id: str
    algorithm_version: str
    feature_version: str
    train_start: date
    train_end: date
    cutoff_ts: datetime
    n: int
    median: float
    scale: float
    scale_method: str
    threshold: float
    data_status_note: str | None = None


class ScoreRequest(BaseModel):
    observation_date: date
    feature: str = Field(default="normalized_spread_pct")
    value: float | None = None
    # When value is None, the stored pair feature for the date is used.


class EventOut(BaseModel):
    id: str
    date: str
    pair_id: str | None
    category: str
    severity: str
    title: str
    description: str
    data_status: str = "VERIFIED"


class IngestionReport(BaseModel):
    run_id: str
    mode: str
    parser_version: str
    overall_status: str
    counts: dict
    errors: list = []
    started_at: datetime | None = None
    completed_at: datetime | None = None


class QualityReport(BaseModel):
    run_id: str | None
    overall_status: str
    counts: dict
    by_class: dict = {}
    by_symbol: dict = {}
    date_ranges: dict = {}
    rejection_reasons: dict = {}
    source_status_totals: dict = {}


class DashboardSummary(BaseModel):
    contracts: list[dict]
    data_status: str
    data_freshness: dict = {}
    source_quality: dict = {}
    top_signals: list[SignalOut] = []
    generation_note: str = (
        "Derived from activity-report data (provisional); not a live MCX feed."
    )
