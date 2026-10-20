# Final Handoff — MCX Gold Intelligence Backend (Hack in Hills '26, PS-03)

## 1. Final architecture

Modular monolith, as specified in the TRD:

```
backend/
├── app/
│   ├── main.py                 # FastAPI factory: CORS, JSON logging, error handlers, routers
│   ├── core/                   # settings, JSON logging, errors, canonical pair domain
│   ├── api/v1/routes/          # health, contracts, comparisons, signals, model, events, backtests, ingestion, dashboard
│   ├── schemas/                # Pydantic DTOs
│   ├── models/                 # source / market / evaluation SQLAlchemy models
│   ├── db/                     # engine + session, base, schema bootstrap
│   ├── ingestion/              # discovery+sha256, sniffing, parsers, classification, pipeline
│   ├── analytics/              # normalize (contract master), features, signal evaluation
│   ├── anomaly/                # robust_mad_v1 baseline + calibration/scoring service
│   ├── backtesting/            # walk-forward engine
│   └── services/               # market_builder (normalized prices, contract inventory)
├── scripts/import_sources.py   # scan → import → market build CLI
├── tests/                      # 59 pytest cases
├── storage/                    # backend-owned SQLite DB + logs (outside source root)
├── .env.example, requirements.txt, pyproject.toml, README.md
```

Frontend additions only (preserving all existing pages/components/data):
`src/services/{apiClient,dataSource,compatibility,contractsService,comparisonService,signalsService,modelService,backtestService,ingestionService}.ts`
plus a small inline backend overlay in the Comparison page that is **inactive in local mode**.

## 2. Database setup and migrations

- Local dev (default, no server needed): `DATABASE_URL=sqlite:///./storage/mcx_gold_dev.db`
- PostgreSQL (documented + driver installed): `DATABASE_URL=postgresql+psycopg://mcx_app:<pw>@localhost:5432/mcx_gold`
- Quick schema stamp: `.venv\Scripts\python scripts\import_sources.py` (idempotent, creates missing tables)
- Alembic workflow (portable migrations for production): `alembic init alembic` → `alembic revision --autogenerate` → `alembic upgrade head`

## 3. Environment configuration

All variables documented in `backend/.env.example` (no secrets committed).
Frontend: `VITE_DATA_MODE=local|api|hybrid`, `VITE_API_BASE_URL` (defaults local, `http://127.0.0.1:8000`).

## 4. Startup commands

```bat
:: backend (http://127.0.0.1:8000, docs at /docs, health at /health/live, /health/ready)
cd backend
python -m venv .venv                                   :: once
.venv\Scripts\pip install -r requirements.txt          :: once
.venv\Scripts\python scripts\import_sources.py         :: once (idempotent)
.venv\Scripts\python -m uvicorn app.main:app --port 8000

:: frontend (http://127.0.0.1:5173)
npm run dev            :: local demo mode (default)
VITE_DATA_MODE=api npm run dev         :: backend as source of truth
VITE_DATA_MODE=hybrid npm run dev      :: backend when reachable, explicit local fallback label
```

## 5. Data-ingestion procedure

Manual-first (no scheduler before manual reliability, per scope): CLI script or `POST /api/v1/ingestion/scan` + `POST /api/v1/ingestion/import` (admin-guarded; open in `APP_ENV=development`). Every run re-verifies source SHA-256 hashes; nothing is ever written under `GoldMcx_Data/` ( asserted by tests and re-checked: 125 files, 0 artifacts created).

## 6. Test results (actually executed)

- Backend: **59 passed** (`pytest tests --disable-warnings` after every change round).
- Frontend: `npm run build` (tsc strict + Vite) passes; app verified rendering with all original components in local mode via browser DOM snapshot.
- Source immutability: 125 files re-hashed before/after import — unchanged; no files generated inside the source root.
- Live pipeline against the real corpus: 125 files → 96 ACTIVITY_REPORT + 8 OPTIONS + 21 CONTRACT_SPEC; 7,378 PROVISIONAL normalized prices; features for all six canonical pairs; calibration `n=1908, median 0.5556, MAD scale 0.4912` for GOLDM–GOLDPETAL (2018→2025); walk-forward backtest executed and stored with cost/benchmark metrics.

## 7. Outstanding limitations (explicit, by design)

1. **No OHLC/settlement/expiry/OI data exists in the supplied corpus.** All market values are activity-implied (`value/lakhs ÷ lots`) and status `PROVISIONAL`. `futures_bars` stays empty (never fabricated). Expiry checks return `UNSCORABLE`; days-to-expiry is 0/unknown in mapped demo fields.
2. Contract specs verified only from the earliest supplied PDFs (GOLDM from May-2026 doc; GOLDTEN/GOLDPETAL Apr-2025; GOLDGUINEA Jan-2025 → Jul-2026 with tender-period change captured as an event).
3. Signals derive from one feature (normalized spread); volume/OI ratios and liquidity are proxy-level only.
4. Backtests run synchronously (sufficient for corpus size); larger data would need the run-ID/status pattern.
5. SQLite default in local dev; PostgreSQL recommended but no server was available on this machine.
6. Demo purity values in `src/data/contracts.ts` (Guinea 916/7.7 g rule) conflict with verified PDFs (8 g @ 999 purity) — preserved as demo data, corrected in the backend contract master.

## 8. Roadmap

1. Swap activity-implied prices for real bhavcopy OHLC when MCX bhavcopy exports are added (pipeline already keys on `futures_bars` with expiry identity).
2. Add second algorithm (Isolation Forest) behind the existing scoring interface with identical chronological splits.
3. Alembic-managed PostgreSQL deploy + docker-compose service.
4. Scheduled ingestion (only after manual flow remains reliable in production use).
5. Per-trade equity curve + drawdown in backtest metrics; parametric cost sensitivity report.
