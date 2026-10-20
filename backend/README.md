# MCX Gold Intelligence — Backend

FastAPI modular monolith for contract-aware relative-value analytics over MCX
gold futures (`GOLDM`, `GOLDTEN`, `GOLDGUINEA`, `GOLDPETAL`). Reads the
original `GoldMcx_Data/` folder **read-only**, stages parsed rows with full
provenance, and exposes versioned analytics APIs. Nothing is ever written into
the source data folder.

## Layout

- `app/api/v1/routes/` — HTTP layer (health, contracts, comparisons, signals, model, events, backtests, ingestion, dashboard)
- `app/core/` — settings, logging, errors, canonical pair domain
- `app/db/` — engine/session, declarative base, schema bootstrap
- `app/models/` — SQLAlchemy models (source registry, market rows, analytics, evaluation)
- `app/schemas/` — Pydantic request/response DTOs
- `app/ingestion/` — discovery/hashing, content sniffing, parsers, classification, import pipeline
- `app/analytics/` — normalization, pair features, signal evaluation
- `app/anomaly/` — robust MAD baseline + calibration/scoring service
- `app/backtesting/` — walk-forward engine
- `tests/` — pytest suite (59 tests)
- `storage/` — backend-owned SQLite dev DB + logs (never inside the source root)
- `scripts/import_sources.py` — scan → import → market build CLI

## Setup

```bat
cd backend
python -m venv .venv
.venv\Scripts\pip install -r ..\requirements.txt   # or: pip install -e .
copy .env.example .env                              # then edit as needed
```

Python 3.11+ is required (developed against 3.13).

## Database

- `DATABASE_URL` selects the backend (SQLAlchemy 2 URL).
- Local development default: `sqlite:///./storage/mcx_gold_dev.db` (auto-created).
- PostgreSQL (recommended for shared deployments; server not required for local dev):
  `DATABASE_URL=postgresql+psycopg://mcx_app:<password>@localhost:5432/mcx_gold`

Alembic workflow (portable migrations):

```bat
cd backend
.venv\Scripts\alembic init alembic        # once; point sqlalchemy.url at DATABASE_URL
.venv\Scripts\alembic revision --autogenerate -m "mcx core"
.venv\Scripts\alembic upgrade head
```

For a quick local start the app can also stamp the schema directly:

```bat
.venv\Scripts\python -c "from app.db.session import get_engine; from app.db.migrations import ensure_schema; print(ensure_schema(get_engine()))"
```

## Run

```bat
cd backend
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Liveness (no DB dependency): `GET http://127.0.0.1:8000/health/live`
- Readiness (checks DB): `GET http://127.0.0.1:8000/health/ready`
- OpenAPI docs: `http://127.0.0.1:8000/docs` (JSON at `/openapi.json`)

CORS is limited to the origins in `CORS_ORIGINS` (no wildcard + credentials).

## Data ingestion (manual, idempotent)

```bat
cd backend
.venv\Scripts\python scripts\import_sources.py            # scan + import + market build
.venv\Scripts\python scripts\import_sources.py --reset    # drops backend tables first
```

Or over HTTP (admin context; `x-admin-token` header outside `APP_ENV=development`):

```http
POST /api/v1/ingestion/scan
POST /api/v1/ingestion/import
GET  /api/v1/ingestion/runs/{run_id}
GET  /api/v1/ingestion/quality-report
```

Guarantees:

- Source files are SHA-256 checksummed at registration and re-verified after import; a mismatch is logged and reported.
- No file inside the source root is ever created, modified, renamed or deleted.
- `.xls` files in the corpus are HTML tables — the sniffer detects content, never the extension.
- Rows are staged (`raw_source_rows`) with validation status and reasons; rejected rows are visible, never silently dropped.
- OPTFUT (options) rows land in `options_daily`, never in futures activity; activity reports never produce OHLC bars.
- Imports are idempotent: unchanged files are skipped; re-runs upsert, not duplicate.

## Model usage

```http
POST /api/v1/model/pairs/GOLDM-GOLDPETAL/calibrate   {"train_end": "2025-06-01"}
POST /api/v1/model/pairs/GOLDM-GOLDPETAL/score       {"observation_date": "2025-06-05"}
```

- Calibration is pair-specific, deterministic and strict: training observations are strictly before `train_end`; the scored observation can never be a member of its own training sample (guarded).
- Output includes algorithm version, calibration window, median, scale + scale method (`mad` | `iqr` | `floor`), robust z, score, severity, explanation and warnings.
- Recipe: `POST /api/v1/backtests/run {"pair_id": "GOLDM-GOLDPETAL", "start": "2024-01-01", "end": "2025-06-30"}`.

## Tests

```bat
cd backend
.venv\Scripts\python -m pytest tests --disable-warnings
```

Covers: content sniffing (HTML-as-XLS), classification (OPTFUT excluded; zero-lot rejections), idempotent imports, source immutability, hand-calculated normalization, all six canonical pairs + `REST-GOLDPETAL` alias, MAD/IQR/floor scaling, threshold boundary, calibration isolation (no scored observation inside its own training sample), pair-feature date alignment, backtest cost arithmetic, reproducibility, benchmark separation, and API behaviour (validations, alias handling, signals dispositions, health endpoints).

## Known limitations (also surfaced by the API itself)

1. The supplied corpus contains **activity reports only** — no OHLC/settlement/expiry/OI. So:
   - `futures_bars` stays empty by design (no fabricated prices).
   - All prices/derived values are **activity-implied** (`Total Value (Lakhs) × 1e5 / Lots`) and labelled `PROVISIONAL`; they are averages across all traded contracts of a symbol per day (no expiry dimension).
   - Expiry-window and depth checks report `UNSCORABLE`, not guesses.
2. The contract-spec master is seeded from the supplied PDFs (hence spec versions start at the earliest provided documents: Gold Mini May-2026, Ten/Petal Apr-2025, Guinea Jan-2025).
3. Local development uses SQLite by default; PostgreSQL is one config change away.
4. No automated scheduler in this release; ingestion is manual-first by design (PR-12 scope).
