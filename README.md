# MCX Gold Intelligence — Backend

**Contract-aware relative-value analytics for MCX gold futures**  
**Hack in Hills ’26 · Problem Statement 03 — Commodity Derivatives Intelligence**

MCX Gold Intelligence is a FastAPI-based modular monolith for analysing relative pricing relationships across four MCX gold futures instruments: `GOLDM`, `GOLDTEN`, `GOLDGUINEA`, and `GOLDPETAL`.

The backend provides source-file discovery and validation, auditable ingestion, contract-specification management, normalized-price and pair-feature calculations, robust statistical novelty scoring, explainable signal evaluation, and walk-forward backtesting APIs. It is designed to serve the existing React + TypeScript frontend without requiring a visual redesign.

> **Data-quality notice:** The supplied source corpus currently contains activity reports and contract-specification documents, but no verified contract-level OHLC/settlement history with expiry and open-interest fields. Activity-derived price proxies are therefore labelled `PROVISIONAL`. They must not be presented as verified MCX settlement prices or as evidence of a tradable edge.

---

## 1. Product scope

The backend supports the following workflow:

1. Discover and fingerprint source files.
2. Detect the actual file format, including HTML tables saved with an `.xls` extension.
3. Parse records into a staging layer and retain provenance and validation outcomes.
4. Classify source data so futures prices, aggregate activity reports, options records, contract specifications, and illustrative demo data remain distinct.
5. Maintain effective-dated contract specifications.
6. Calculate normalized values and pairwise relative-value features when the input data supports those calculations.
7. Calibrate and score observations using a robust median/MAD novelty-detection baseline.
8. Evaluate signals separately from their statistical anomaly classification.
9. Run reproducible, chronological backtests with explicit assumptions.
10. Expose versioned APIs to the existing frontend.

The system is an analytical product, not a broker, order-execution system, or financial-advice service.

## 2. Architecture and repository layout

The application uses a modular-monolith architecture. HTTP routing, data ingestion, analytics, anomaly scoring, persistence, and backtesting are separated by responsibility while remaining in one deployable backend.

```text
backend/
├── app/
│   ├── api/v1/routes/   # HTTP endpoints: health, contracts, comparisons,
│   │                    # dashboard, signals, model, events, backtests, ingestion
│   ├── core/             # Configuration, logging, errors, canonical pair rules
│   ├── db/               # SQLAlchemy engine/session and schema utilities
│   ├── models/           # Persistence models for source, market and evaluation data
│   ├── schemas/          # Pydantic API request/response schemas
│   ├── ingestion/        # Discovery, hashing, format sniffing, parsing and classification
│   ├── analytics/        # Normalization, feature engineering and signal evaluation
│   ├── anomaly/          # Robust statistical baseline and calibration/scoring service
│   ├── backtesting/      # Walk-forward backtesting engine
│   ├── services/         # Shared market-data construction services
│   └── main.py           # FastAPI application entry point
├── alembic/              # Database migrations
├── scripts/
│   └── import_sources.py # Scan → import → market-data build
├── tests/                # Automated test suite
├── storage/              # Backend-owned local database/logs; never source data
├── .env.example          # Configuration template
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

The source data folder (default: `GoldMcx_Data/` at the repository root) is an **immutable input**. Generated files, logs, staging data, converted data and databases belong in backend-owned storage, never in the source directory.

## 3. Technology stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Validation and configuration | Pydantic, Pydantic Settings |
| Persistence | SQLAlchemy 2, SQLite for local development, PostgreSQL for shared deployments |
| Schema migrations | Alembic |
| Data processing | Pandas, NumPy |
| Source formats | BeautifulSoup, lxml, xlrd, pypdf |
| Database connectivity | Psycopg for PostgreSQL |
| Testing | pytest, HTTPX |
| Frontend integration | Existing React, TypeScript, Vite application over REST APIs |

Python **3.11 or later** is required. Development has been performed with Python 3.13.

## 4. Prerequisites

- Python 3.11+
- The repository cloned or available locally
- The source data folder, if running ingestion
- PostgreSQL only if you choose PostgreSQL instead of the local SQLite database

The default local-development configuration uses SQLite; a PostgreSQL server is not required for a basic local start.

## 5. Local setup — Windows PowerShell

Run the following commands from the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Review `.env` and verify `MCX_DATA_DIR` points to the existing source folder. The default is `../GoldMcx_Data`, resolved as a path relative to the backend configuration's repository-root convention.

Do not place credentials or private values in committed files.

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

## 6. Configuration

The main configuration variables are defined in `backend/.env.example`.

| Variable | Purpose | Default / example |
|---|---|---|
| `APP_ENV` | Runtime environment | `development` |
| `API_PREFIX` | Versioned API prefix | `/api/v1` |
| `DATABASE_URL` | SQLAlchemy connection URL | `sqlite:///./storage/mcx_gold_dev.db` |
| `CORS_ORIGINS` | Explicit allowed frontend origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `MCX_DATA_DIR` | Read-only source-data root | `../GoldMcx_Data` |
| `DATA_WRITE_MODE` | Source-folder write policy | `read_only` |
| `LOG_LEVEL` | Application logging level | `INFO` |
| `IMPORT_MAX_FILE_MB` | Maximum accepted import file size | `50` |
| `DEMO_FALLBACK_ENABLED` | Allow the frontend's configured local-demo fallback | `true` |

### Database configuration

**SQLite (local development)**

```dotenv
DATABASE_URL=sqlite:///./storage/mcx_gold_dev.db
```

The database file is stored in backend-owned storage. The backend must never write to the source data root.

**PostgreSQL (shared development or deployment)**

```dotenv
DATABASE_URL=postgresql+psycopg://mcx_app:<password>@localhost:5432/mcx_gold
```

Create the PostgreSQL database and account before starting the application with this URL. Store real credentials only in an appropriate local environment file or secret manager.

### CORS

CORS is configured through `CORS_ORIGINS`. Keep the list limited to the frontend origins in use. Do not combine wildcard origins with credentialed requests.

## 7. Database initialization and migrations

The repository already contains an Alembic configuration and an initial migration. **Do not run `alembic init` again.**

From the `backend/` directory, apply the existing migrations:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

On macOS/Linux:

```bash
.venv/bin/alembic upgrade head
```

If the local development workflow is configured to initialize the schema directly, the following helper is also available:

```powershell
.\.venv\Scripts\python.exe -c "from app.db.session import get_engine; from app.db.migrations import ensure_schema; print(ensure_schema(get_engine()))"
```

Use Alembic migrations as the standard path when managing schema changes. Do not create a new initial migration or run destructive schema operations simply to start the application.

## 8. Run the API

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

macOS/Linux:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The local API is available at `http://127.0.0.1:8000`.

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Liveness check; does not require a database connection |
| `GET /health/ready` | Readiness check, including database availability |
| `GET /openapi.json` | OpenAPI schema |
| `GET /docs` | Interactive Swagger UI |

Use the readiness endpoint to confirm that required dependencies are reachable. A successful liveness response alone does not prove that the database is ready.

## 9. Source-data ingestion

Ingestion is **manual-first and idempotent**. It scans the configured source root, fingerprints source files, detects content types, parses and classifies records, validates data, stores staging results, and builds supported market-derived records.

### Run the import pipeline

From `backend/`:

```powershell
.\.venv\Scripts\python.exe scripts\import_sources.py
```

macOS/Linux:

```bash
.venv/bin/python scripts/import_sources.py
```

The command performs the scan, import, and market-data build workflow. Review its report and the quality-report API before interpreting resulting analytics.

### Ingestion API

The versioned ingestion endpoints are:

```http
POST /api/v1/ingestion/scan
POST /api/v1/ingestion/import
GET  /api/v1/ingestion/runs/{run_id}
GET  /api/v1/ingestion/quality-report
```

Outside development mode, HTTP ingestion operations require the configured administrative context, including the `x-admin-token` header where applicable. Do not expose administrative import or reset operations to an unauthenticated public interface.

### Ingestion controls

- Source files are SHA-256 fingerprinted and re-verified after import.
- The pipeline must not create, modify, rename or delete anything inside the source root.
- File format is determined from content; files with an `.xls` suffix may contain HTML tables rather than native Excel workbooks.
- Parsed records are staged in `raw_source_rows` with validation status and reasons.
- Rejected records remain auditable instead of being silently discarded.
- `OPTFUT` options records are stored separately from futures activity.
- Aggregate activity reports do not generate contract-level OHLC bars.
- Re-importing an unchanged source file is skipped; supported reruns are designed to upsert records instead of duplicating them.

### Destructive reset warning

The import script supports a reset option:

```powershell
.\.venv\Scripts\python.exe scripts\import_sources.py --reset
```

This option drops backend tables before rebuilding them and may destroy locally stored imported or derived records. Use it only for a disposable development database after confirming the configured database URL. **Never run it against a shared or production database without an approved backup and recovery plan.** It must not modify source files.

## 10. Normalization and contract handling

Contract specifications are effective-dated and include their source document and verification status. The current contract master covers:

| Symbol | Trading unit | Quoted basis | Purity |
|---|---:|---:|---:|
| `GOLDM` | 100 g | 10 g | 995 |
| `GOLDTEN` | 10 g | 10 g | 999 |
| `GOLDGUINEA` | 8 g | 8 g | 999 |
| `GOLDPETAL` | 1 g | 1 g | 999 |

These values are recorded in the code from the supplied contract-specification documents. Historical validity is limited by the earliest available document for each instrument; a current specification must not be assumed valid for all earlier dates without evidence.

The normalization service applies only known quote rules. Unsupported quote rules raise an error rather than being silently processed as if they were standard. Where a specification is not verified for the observation date, the derived value must remain provisional.

The system distinguishes an instrument symbol from an expiry-dated contract. It must not treat the near-month contract as one continuous series without explicitly handling the roll between expiries.

## 11. Canonical contract pairs

The backend supports six unique unordered pairs:

- `GOLDM-GOLDTEN`
- `GOLDM-GOLDGUINEA`
- `GOLDM-GOLDPETAL`
- `GOLDTEN-GOLDGUINEA`
- `GOLDTEN-GOLDPETAL`
- `GOLDGUINEA-GOLDPETAL`

The legacy frontend identifier `REST-GOLDPETAL` is accepted as a compatibility alias for `GOLDGUINEA-GOLDPETAL`. The backend uses the canonical identifier internally and does not create a seventh pair. Unknown pair IDs should return an explicit validation error, not silently map to another pair.

Pair features are built only when both legs have observations on the same trade date. Missing dates are counted; observations are not forward-filled to manufacture a comparison.

## 12. Novelty detection and model API

The initial implementation uses a robust statistical baseline based on pairwise spread observations. It is a novelty-detection baseline, not an Isolation Forest model.

### Calibration and scoring examples

```http
POST /api/v1/model/pairs/GOLDM-GOLDPETAL/calibrate
Content-Type: application/json

{"train_end":"2025-06-01"}
```

```http
POST /api/v1/model/pairs/GOLDM-GOLDPETAL/score
Content-Type: application/json

{"observation_date":"2025-06-05"}
```

Calibration is pair-specific and deterministic. Training observations must be strictly earlier than the calibration cutoff. The observation being scored must not appear in its own calibration sample.

Score responses include the algorithm version, calibration window, median, scale and scale method (`mad`, `iqr`, or `floor`), robust z-score, anomaly score, severity, explanation and data-quality warnings.

A high score means that an observation is unusual relative to the configured calibration sample. It is **not** a probability of mispricing or profit, and it is not by itself a trading recommendation.

## 13. Signals and post-detection evaluation

The backend deliberately separates statistical classification from the final signal disposition.

An observation may be statistically anomalous but still be `WATCH`, `IGNORE`, or `UNSCORABLE` because expiry, data quality, liquidity information or execution-cost information is missing or unsuitable.

The current activity-report corpus does not include expiry dates, executable prices, or order-book depth. Consequently:

- Expiry validation is `UNSCORABLE` where expiry is unavailable.
- Liquidity evaluation must not equate trading volume with market depth.
- Cost assumptions are not verified execution costs.
- A settlement or activity-derived value must not be described as an executable fill.

Missing information is surfaced as a limitation rather than replaced with fabricated confidence.

## 14. Walk-forward backtesting

A backtest can be requested with the API, for example:

```http
POST /api/v1/backtests/run
Content-Type: application/json

{
  "pair_id": "GOLDM-GOLDPETAL",
  "start": "2024-01-01",
  "end": "2025-06-30"
}
```

The implementation is intended to support chronological replay, explicit cost assumptions, reproducible run configuration and separation of relative-value performance from general gold-market movement.

Backtest results must use eligible observations and preserve the actual contract identity and expiry assumptions. A result is not a verified performance claim when the inputs are provisional or the execution assumptions cannot be supported.

Do not interpret illustrative frontend backtest values as backend-computed performance.

## 15. Frontend integration

The existing application is a React + TypeScript + Vite frontend. The backend is designed to supply its contracts, price series, comparisons, signal records, model results, events and backtest results through versioned APIs.

Configure CORS using the frontend origins listed in `.env`. If the frontend offers local, API and hybrid data modes, keep that choice explicit and visible in its configuration. Static educational content may remain frontend-local, while supported market and analytics responses come from the API.

Recommended local development ports:

- Frontend: `http://localhost:5173`
- Backend: `http://127.0.0.1:8000`

A liveness test can be performed with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

To verify integration rather than backend availability alone, inspect the browser's Network panel and confirm that frontend interactions issue requests to the backend and receive the expected JSON responses.

## 16. Automated tests

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests --disable-warnings
```

macOS/Linux:

```bash
.venv/bin/python -m pytest tests --disable-warnings
```

The test suite is designed to cover:

- Content detection, including HTML tables saved as `.xls`.
- Source classification and exclusion of options from futures activity.
- Rejection of zero-lot/invalid rows where price derivation is not possible.
- Idempotent imports and source-file immutability.
- Hand-calculated normalization cases.
- All six canonical pairs and the legacy `REST-GOLDPETAL` alias.
- MAD, IQR and floor-scale handling.
- Threshold-boundary behaviour.
- Calibration isolation and prevention of scored-observation leakage.
- Pair-feature date alignment and missing-leg handling.
- Backtest cost calculations, reproducibility and benchmark separation.
- API validation, signal disposition, and health endpoints.

The repository README has previously documented 59 tests. Always run the current suite and report the actual result for the current checkout; do not assume that an earlier test count or result still applies after changes.

## 17. Current limitations and data-quality status

The current source corpus is activity-report data and contract-specification PDFs. It does **not** contain verified contract-level OHLC/settlement, expiry and open-interest history for the four target futures symbols.

As a result:

1. `futures_bars` remains empty unless appropriate futures price records are imported.
2. Activity-implied values use `Total Value (Lakhs) × 100,000 ÷ Lots` and are labelled `PROVISIONAL`. They are aggregate averages for a symbol and date, not prices for a particular expiry-dated contract.
3. Pair features built from activity-implied values are provisional and must not be represented as settlement-price spreads.
4. Expiry-window and order-book-depth checks return `UNSCORABLE` where required data is unavailable.
5. Contract-specification history starts at the earliest supplied document for each instrument. Earlier periods must not be described as verified without additional source evidence.
6. Local development uses SQLite by default; PostgreSQL is available through `DATABASE_URL` when a server is configured.
7. Ingestion is manual-first. No automated scheduler is included in the current release.

### Data required to validate the full product

The next material data improvement is to obtain MCX Bhavcopy records that contain, at minimum, trade date, symbol, expiry date, Open, High, Low, Close/settlement, volume, and open interest for the actual futures contracts. The importer must validate the source date and contract identity and must not silently construct a continuous series across expiries.

Official reference pages:

- [MCX Bhavcopy](https://www.mcxindia.com/market-data/bhavcopy)
- [MCX Gold contract specifications](https://www.mcxindia.com/products/bullion/gold)

Availability and formats of official files may change; verify them when collecting new data.

## 18. Operational and analytical safeguards

- Keep `.env` and secrets out of version control.
- Restrict ingestion and reset operations to the intended development/admin context.
- Never mutate source data.
- Keep provisional, verified, rejected, and illustrative records distinguishable.
- Record the provenance and version of derived analytics.
- Avoid look-ahead leakage in calibration and backtesting.
- Do not equate aggregate activity with market depth.
- Do not claim a profitable strategy without a defensible, cost-aware, out-of-sample evaluation.
- Prefer explicit `UNSCORABLE` outcomes over guessed values.

## 19. Development workflow

For changes to the backend:

1. Review the affected source and schema.
2. Add or update tests with the implementation.
3. Apply database migrations in the intended development environment.
4. Run the relevant tests and then the full test suite.
5. Verify source-file checksums when ingestion code changes.
6. Review API responses and frontend integration in the browser.
7. Update this README when setup steps, endpoints, data sources, or limitations change.

The backend is considered reliable only when the observed test results, data-quality report, and analytical assumptions support that conclusion—not merely because the API starts successfully.
