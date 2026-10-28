# SETUP — MCX Gold Intelligence (Code Paradox)

**Single start-here guide.** Everything a new developer needs from a clean checkout:
environment, database, market-data providers, model training, daily operations, and debugging.

> This is an **analytical research product** (Hack in Hills '26 · PS-03), not a broker, order-routing
> system or investment-advice service. All "signals" are statistical anomaly observations on
> relative-value features, clearly versioned, and never executed against the market.

---

## A. Prerequisites and clean checkout

| Tool | Version | Notes |
|------|---------|-------|
| Python | **>= 3.11** | tested on 3.11/3.12 |
| Node.js | >= 20 (npm >= 10) | frontend + tests |
| Git | any recent | |
| OS | Windows 10/11, macOS, Linux | repository data paths validated on Windows |

### 1. Clone and enter

```bash
git clone <repo-url> mcx-gold
cd mcx-gold
```

### 2. Python virtual environment

```bash
python -m venv .venv
# Windows (Git Bash):  source .venv/Scripts/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate

python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt   # pytest etc.
python --version   # must print 3.11+ or 3.12
```

`requirements.txt` pins the runtime stack: FastAPI, SQLAlchemy 2, Alembic, pandas, numpy,
**scikit-learn >= 1.5**, **joblib >= 1.3**, psycopg 3 (Supabase PostgreSQL driver),
httpx (provider adapters), beautifulsoup4/lxml (source parsing).

### 3. Frontend dependencies

```bash
npm install
npm run build       # tsc --noEmit && vite build — must pass on a clean checkout
```

### 4. Folder map (actual layout)

```text
repo-root/
├── ml/              # root ML package: data collection, features, training, artifacts
│   ├── artifacts/   # generated .joblib model bundles (gitignored)
│   └── reports/     # generated quality/evaluation reports (gitignored)
├── backend/         # FastAPI + SQLAlchemy 2 + Alembic modular monolith
│   ├── app/         # routes, models, providers, ingestion, analytics, anomaly
│   ├── alembic/     # additive migrations only — never re-init
│   └── tests/       # pytest suite
├── src/             # React + TypeScript + Vite + Tailwind frontend
├── SETUP.md         # this file
└── README.md
```

### 5. Verify the toolchain

```bash
python -c "import sklearn, joblib, fastapi, sqlalchemy; print('backend deps ok')"
npm run build
```

---

## B. Supabase PostgreSQL (shared/runtime database)

The backend and all ML jobs read/write **one shared database**. For deployed/shared work this is
**Supabase PostgreSQL** (SQLAlchemy 2 + Alembic). A local SQLite file is supported for isolated
development/tests only and is the `.env.example` default.

### 1. Create the project

1. Sign up at <https://supabase.com> and create a project (any region near you).
2. Open **Project Settings → Database**.

### 2. Which connection string to use

| Purpose | Port | Variable | Notes |
|---------|------|----------|-------|
| App runtime (FastAPI, ML jobs) | **6543** (transaction pooler) | `DATABASE_URL` | pooled, IPv4; safe for many short-lived sessions. Not for session locks. |
| Migrations / admin | **5432** (direct or session pooler) | `MIGRATION_DATABASE_URL` | long-lived connections for `alembic upgrade head` |

Credentials in the URL must be **URL-encoded** (e.g. `@` → `%40`, `:` → `%3A`).
Pattern (`<ref>` is your project reference, password is your DB password):

```ini
DATABASE_URL=postgresql+psycopg://postgres.<ref>%3A<encoded-wrong-do-not-mix>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

⚠️ Format precisely: `postgres.<PROJECT_REF>` is the **user**; password goes **after the single
colon** and must be URL-encoded. Correct example:

```ini
DATABASE_URL=postgresql+psycopg://postgres.abcdefghjk:my%40password@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
MIGRATION_DATABASE_URL=postgresql+psycopg://postgres.abcdefghjk:my%40password@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

### 3. Backend `.env`

Copy the template and fill in real values (never commit the real file — `backend/.env` is gitignored):

```bash
cd backend
cp .env.example .env
```

```ini
APP_ENV=development                      # never "production" locally unless deliberate
DATABASE_URL=<runtime pooler URL from §B.2, or sqlite:///./storage/mcx_gold_dev.db>
MIGRATION_DATABASE_URL=<direct URL from §B.2>          # only if migrations need it
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MCX_DATA_DIR=<root of the source-data corpus>            # opened read-only, enforced
DATA_WRITE_MODE=read_only                                # fixed guard — do not change
DEMO_FALLBACK_ENABLED=false                              # real frontend shows real states only
# REDIS_URL=redis://localhost:6379/0                     # optional shared cache
```

Notes:

- `CORS_ORIGINS` must list the **exact** frontend origins the browser will use. Never `*`.
- The **browser never talks to Supabase**. Only `VITE_API_BASE_URL` (public, no secrets) reaches the
  frontend; vendor/DB credentials live server-side in `backend/.env` or deployment secrets.

### 4. Apply migrations

Run from the `backend/` directory with the activated venv:

```bash
cd backend
python -m alembic upgrade head          # additive migrations; never re-run `alembic init`
```

Verify catalogue state:

```bash
python -m alembic current               # shows the head revision applied
```

### 5. Start the backend

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- **Readiness** (data/DB/providers actually usable):
  <http://127.0.0.1:8000/health/ready> — check before trusting data pages.
- **Liveness**: <http://127.0.0.1:8000/health/live>.
- OpenAPI docs: <http://127.0.0.1:8000/docs>.

If `backend/.env` is missing a required value the settings module fails fast with a named variable,
not a silent default. See §F for the error shape.

---

## C. Market data — providers, sources, entitlements

### What we use and why

| Source | Type | Key needed | Used for |
|--------|------|-----------|----------|
| **MCX daily Bhavcopy** — <https://www.mcxindia.com/market-data/bhavcopy> | official EOD per contract | no | daily bars: Symbol, ExpiryDate, Open/High/Low/Close, Volume, OpenInterest |
| **MCX gold contract specs** — <https://www.mcxindia.com/products/bullion/gold> | trading unit, quote base, purity, expiry rules | no | normalization references, spec provenance |
| **TrueData** — <https://www.truedata.in> | licensed live + history | yes (login/password with MCX entitlement) | live quotes, intraday history |
| **AccelPix PIX API** | licensed quotes/history | yes (API key with entitlement) | live quotes, intraday history |
| **Direct MCX live feed** | separately authorized feed | operator-supplied credentials | not enabled by default; blocked until credentials are supplied |

Hard rule: **no source is marked "configured" unless real credentials/entitlements exist.**
With only MCX EOD, the UI shows *“EOD data — no intraday feed configured”* — never “Live”.

### MCX EOD Bhavcopy (no key)

The adapter downloads the daily file per session, validates that the **response date matches the
requested trade date** in `Asia/Kolkata` (holidays, unpublished files, padded symbols and compact
expiries like `04SEP2026` are handled explicitly), and upserts validated rows idempotently into the
`provider_daily_bar` table keyed by `(symbol, expiry_date, trade_date, provider)`. Re-running a
known session updates rather than duplicates.

Enable in `backend/.env`:

```ini
MCX_EOD_ENABLED=true
MCX_BHAVCOPY_BASE=https://www.mcxindia.com/backup/bhavcopy/BhavCopy_MCX_
```

Trigger one EOD sync manually:

```bash
python -m ml.jobs --days 10        # idempotent; safe to rerun; exits non-zero on failure
```

### TrueData (`MARKET_DATA_PROVIDER=truedata`)

1. Register at <https://www.truedata.in> and subscribe to a plan that includes **MCX** data at the
   required resolutions.
2. Put credentials in `backend/.env`:

```ini
TRUEDATA_LOGIN_ID=your_login
TRUEDATA_PASSWORD=your_password          # never committed; logs redact secrets
TRUEDATA_LIVE_URL=push.truedata.in       # from vendor docs (verify current values)
TRUEDATA_LIVE_PORT=8082
```

3. Symbols/tickers the vendor uses must be **verified** before the feed worker subscribes:
   mappings are first persisted as unverified candidates (`provider_instruments.verified=False`)
   and an admin review flow records who/when/why. Unverified tickers are **never** subscribed —
   this is enforced and tested.
4. Smoke test (real credentials only — costs a live connection):

```bash
cd backend
python -c "from app.providers.truedata import live_client_probe; print(live_client_probe())"
```

### AccelPix (`MARKET_DATA_PROVIDER=accelpix`)

```ini
ACCELPIX_API_KEY=your_key
ACCELPIX_API_HOST=apidata.accelpix.in
ACCELPIX_SCHEME=https
```

Same rules: entitlement-gated, adapter-verified, operator-reviewed mappings; polling snapshots are
never represented as tick streams.

### Which provider wins (failover)

`MARKET_DATA_PROVIDER` selects the primary. Bars arriving from **both** providers for the same
`(symbol, expiry, trade_date)` are reconciled by provider priority — never averaged — and the
record retains its original source lineage. Any provider outage degrades status
(`NOT_CONFIGURED` / `STALE` / `DEGRADED`) rather than failing the whole job.

> **Redistribution / display rule:** `PUBLIC_MARKET_DATA_DISPLAY=true` only if you have recorded
> vendor approval to show real-time data publicly. Without approval, real-time data is not displayed.

---

## D. ML training and the model artifact

### First training (one command)

From the **repo root** with the venv active:

```bash
python -m ml.train_model --sync-history --mode daily
```

(`--mode` accepts `daily` only. Intraday training is deliberately blocked — it requires genuine
licensed intraday history and is reported as *“collecting data / model not ready”* until then.)

What the command does, in order:

1. `[1/5]` Collects history from every **configured/authorized** source within the lookback window,
   plus data already persisted in the DB. Reports per source: reached / rows / locked (no creds).
2. Validates, deduplicates and persists new history with lineage.
3. Builds a data-quality report and **fails (exit ≠ 0)** with an actionable message if verified
   history is insufficient for training. It never fabricates rows or uses demo/activity proxies.
4. Trains the candidate sklearn pipeline (IsolationForest benchmarked against the robust-MAD
   baseline; OneClassSVM when volume supports it) on chronological windows only — never shuffled.
5. Saves the **fitted preprocessing + estimator bundle** to `ml/artifacts/*.joblib`
   (temp write → fsync → atomic rename), computes SHA-256, and registers version/status in the DB
   (`model_registry`). A failing candidate never replaces the active known-good model.

### Status / retrain / evaluate

```bash
python -m ml.train_model --status            # active + registry status per frequency
python -m ml.train_model --train-only        # retrain from stored data, no re-download
```

An evaluation report is written to `ml/reports/` (gitignored). The API exposes model metadata:

```
GET /api/v1/ml/registry        # active/candidate/failed models with versions + metrics
GET /api/v1/model/status       # runtime readiness of scoring
```

### What “insufficient verified history” means

The supplied corpus contains activity reports (aggregate lots/value), **not verified contract-level
OHLC/settlement history with expiry + OI**. Until real Bhavcopy/provider history covers a usable
window, training **fails by design** with a coverage table. This is the honest behavior; see §F.
If a `robust_mad_v1` baseline is active instead of an ML artifact, the API/labels always say so —
the baseline is never presented as the trained model.

### Model versioning rules (enforced in tests)

- Artifact checksum, feature-schema version, and dependency versions are validated at load;
  mismatches produce an explicit *model unavailable* state instead of silent scoring.
- Active artifact selection comes from **DB metadata**, never a client-supplied path.
- The active production artifact must live on persistent storage (configure `ML_ARTIFACT_DIR`
  or an object store in deployment; local dev uses `ml/artifacts/`).

---

## E. Automated daily + realtime operations

### One-off EOD sync + score

```bash
python -m ml.jobs --days 10       # sync eligible sessions → persist → features → score → publish
```

The job is idempotent (reruns update, never duplicate), skipped sessions are logged as
`already_present`, and a durable run record is stored in `ingestion_run` with counts/errors.
Verify results:

```bash
curl -s http://127.0.0.1:8000/health/ready
curl -s "http://127.0.0.1:8000/api/v1/signals?limit=5"
```

### Production-safe daily schedule

The scheduler is a **standalone command**, never started in every Uvicorn worker:

**cron / systemd timer**

```cron
20 19 * * 1-5 cd /srv/mcx-gold && .venv/bin/python -m ml.jobs --days 10 >> ml/jobs.log 2>&1
```

(MCX session ends ~23:30 IST; Bhavcopy typically publishes ~19:00–20:00 IST. Pick your window after
observing real publish times.)

**Windows Task Scheduler**

- Program: `<venv>\Scripts\python.exe`
- Arguments: `-m ml.jobs --days 10`
- Start in: `<repo-root>`
- Daily trigger, 20:15 IST, weekdays, "Run whether user is logged on or not".

### Running backend + frontend together (two terminals)

```bash
# Terminal 1
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 (repo root)
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env.local
npm run dev            # http://localhost:5173
```

The Vite dev server also **proxies `/api` to `http://127.0.0.1:8000`** so same-origin requests work
even without `VITE_API_BASE_URL`. In the browser DevTools network tab you should see real requests
to `/api/v1/...` returning JSON, plus a long-lived **SSE** connection to
`/api/v1/market/live/stream` (EventSource) receiving `snapshot`, `quote`, `anomaly`,
`provider_status` and `:heartbeat` frames.

### Freshness / status semantics (UI)

- Live quote age is displayed with its **source event time**, not local time.
- `NOT_CONFIGURED` → no credentials; `STALE` → connected but quotes expired (> `LIVE_FEED_STALE_AFTER_S`,
  default 8s); `CONNECTED_WITH_FRESH_DATA` → truly live.
- Model-not-ready → pages show `ML_MODEL_NOT_READY` / baseline-labelling instead of pretending.
- Frontend `DEMO_FALLBACK_ENABLED=false` in all real deployments; a disconnected API shows explicit
  error/retry states, never demo data.

### Tests without leaking credentials

```bash
# backend suite (uses local SQLite fixtures; no vendor keys needed)
cd backend && python -m pytest tests -q

# frontend build + type check
npm run build
```

---

## F. Common errors and recovery

| Symptom | Cause | Fix |
|---------|-------|-----|
| `psycopg.OperationalError: could not translate host` / TLS failure | wrong Supabase host/port | use the **pooler** host for runtime (6543) and direct/session (5432) for migrations; see §B.2 |
| `password authentication failed` | unencoded special chars | URL-encode the password (`@`→`%40`, `:`→`%3A`) |
| `alembic: relation already exists` / head mismatch | manual schema edits | `python -m alembic current` then `upgrade head`; **never** drop tables to force it |
| `MISSING_DB_URL` at startup | `backend/.env` absent | `cp .env.example .env` and fill values |
| `MARKET_DATA_PROVIDER` shows `NOT_CONFIGURED` | no credentials set | expected without a subscription; EOD-only mode is supported |
| provider sync returns rows but alerts don't change | training gated on verified history | run `python -m ml.train_model --sync-history --mode daily`; insufficient data fails loudly by design |
| `joblib` version/schema mismatch in logs | stale artifact | retrain (`--train-only`) or restore matching artifact; scoring is blocked, not silently wrong |
| SSE shows nothing / stale | feed leader not running or no entitlement | check `/api/v1/market/provider/status`; SSE in isolated dev works but quotes require a live provider |
| Redis down / degraded | `REDIS_URL` set but unreachable | app degrades to per-process cache with a visible warning; do not run >1 API worker without Redis |
| Frontend 404s on `/api/...` | backend on different port or stopped | keep uvicorn on 8000, or set `VITE_API_BASE_URL` and restart `npm run dev` |
| Lock timeout / HTTP 409 or 423 | concurrent writers on same pair | automatic bounded retry; if persistent, check for a stuck ingestion worker |

**Things that cannot work without real entitlements:** TrueData/AccelPix live quotes, licensed
intraday history, intraday model training, live tick scoring, real-time alerts. Everything else —
EOD pipeline, model training, backtests, API/SSE, UI states — runs with the local suite and
fixture-only tests, which is exactly what CI runs.

---

*Generated setup guide; keep in sync with `backend/.env.example` and `README.md`.*
