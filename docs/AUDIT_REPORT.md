# Phase 0 — Repository & Data Audit (Gate 0)

Date: 2026-10-20 · Scope inspected: full workspace, PRD/TRD (`MCX_Gold_Intelligence_Backend_{PRD,TRD}.docx`), `src/`, `GoldMcx_Data/` (125 files, inspected **by content**, not extension).

## 1. Repository audit

- **Frontend**: React 18 / TS / Vite / Tailwind / Recharts / Lucide. `src/App.tsx` + 8 page modules (Dashboard, Signals, Contracts, Comparison, Model, Insights, Learn, Events via `EventsBacktestPage`), 14 components, 11 data modules, `src/lib/anomalyScore.ts` (robust median/MAD baseline, threshold 3.5, score = min(|z|/6, 1), IQR/1.349 fallback, scale floor), `src/lib/filters.ts`, `src/types/index.ts` DTO types.
- **Build**: `npm run dev` / `npm run build` (`tsc --noEmit && vite build`). No test tooling on the frontend.
- **Backend status**: none exists — greenfield per TRD layout §2.
- **Package versions** (installed for backend, py3.13.1/win): fastapi 0.149, sqlalchemy 2.1.5, alembic 1.20, pandas 3.0.6, numpy 2.5.4, pypdf 6.21, pytest 9.1, httpx 0.28.

## 2. Source-data inventory (`GoldMcx_Data/`, 125 files, ~20 MB, SHA-256 of every file recorded at import time)

| Top dir | Files | Content (verified) |
|---|---|---|
| Contracts | 21 | Contract-specification PDFs (text-extractable with pypdf) |
| GOLD | 44 | HTML tables saved as `.xls`, Detail/Summary activity reports 2005–2026 |
| GOLDM | 18 | same, 2018–2026 |
| GOLDPETAL | 18 | same, 2019–2026 |
| GOLDGUINEA | 20 | same, 2025–2026 |
| GOLDTEN | 4 | same, 2026 only |
| With Expiry date | 0 | empty directory |

- **Format detection**: every one of the 104 `.xls` files is an **HTML byte stream** (no OLE2/`D0 CF 11 E0` signatures present). No native XLS/XLSX/CSV/PDF-table files exist. Parser strategy: `pd.read_html` after signature sniffing.
- **Detail report columns**: Instrument (FUTCOM/OPTFUT/OPTFUT), Date, Segment, Commodity, Traded Contract (Lots), Total Value (Lakhs), Avg Daily Turnover (Lakhs), Premium Value (Lakhs).
- **Summary report columns**: Instrument, Date, Traded Contract (Lots), Total Value (Lakhs), Premium Value (Lakhs).
- **No OHLC columns exist anywhere. No Expiry column exists anywhere.** Grep for Expiry/Open/High/Low/Last over all `.xls` → 0 hits.
- **Duplicate files**: 0 byte-identical (SHA) duplicates; however Summary vs Detail double counting must be prevented by classification, and `*(1).xls` suffixed files are independent content (different download snapshots), retained as separate sources.

### Data-classification determination (content-verified rules)

| Class | Eligibility for core pipeline |
|---|---|
| `ACTIVITY_REPORT` | The **only** quantitative market data provided. FUTCOM = futures activity; OPTFUT = options activity (classified `OPTIONS`, excluded from futures series). |
| `CONTRACT_SPEC` | 21 PDFs; authoritative source for the contract master (see §4). |
| `FUTURES_PRICE` | **None present.** `futures_bars` (loss/OHLC) cannot be populated from this corpus and will remain empty by design — never fabricated. |
| `ILLUSTRATIVE_DEMO` | `src/data/*.ts` — stays frontend-local, never ingested as market data. |
| `UNSUPPORTED` | none found so far; QA-guard remains. |

**Key audit conclusion**: the supplied corpus cannot support contract-expiry-specific OHLC prices, days-to-expiry, or OI features. The honest analytic substrate is: activity-implied **value-per-lot** (`Total Value (Lakhs) × 1e5 / Lots`) → quoted-price-proxy per `quote_grams` → provisional normalized fine-gram price. Our borderline sanity checks confirm it is economically consistent (GOLDM Jan-2026 ≈ ₹1.35 L/10 g; GOLDTEN Jan-2026 ≈ ₹1.39 L/10 g; GOLDGUINEA Jan-2025 ≈ ₹62k/8 g; GOLDPETAL Jan-2019 ≈ ₹3.1 k/g). All such values are labelled **PROVISIONAL** (activity-derived, not settlement prices) and are excluded from validated-performance claims.

## 3. Frontend preservation notes

- `pairKey()` in `src/data/contracts.ts` **silently falls back** to `GOLDM-GOLDTEN` on unknown pairs — a defect relative to the spec; backend will return explicit 400/404 and the adapter will mirror that in hybrid/api mode (local mode behaviour preserved).
- Legacy alias `REST-GOLDPETAL` = `GOLDGUINEA-GOLDPETAL`.
- Hardcoded demo specs in `src/data/contracts.ts` partially conflict with verified PDFs (Guinea purity 916/7.7 g coin-premium rule vs. verified 8 g quoted at 999 purity).
- Labels honesty: Topbar already states "Illustrative data — not a live MCX feed".
- `GOLDTEN` has only a 4-file/2026 history (short history must be surfaced), `GOLDGUINEA` from 2025, `GOLDPETAL` from 2019, `GOLDM` from 2018, `GOLD` aggregate 2005–2026.

## 4. Verified contract specifications (from the supplied official MCX PDFs, per-contract, extracted with pypdf)

| Symbol | Trading unit | Quotation/Base value | Purity | Effective from | Spec source |
|---|---|---|---|---|---|
| GOLDM | 100 g | 10 g | 995 | contracts from May 2026 document (earliest provided) | gold-mini-may-2026-contract-onwards.pdf |
| GOLDTEN | 10 g | 10 g | 999 | contracts from Apr 2025 document (earliest provided) | gold-ten-april/may-2025…pdf |
| GOLDGUINEA | 8 g | **8 g** | **999** (serially-numbered guinea; final settlement = DDR from Ahmedabad 995 spot × 999/995 × 8/10 — a settlement conversion, **not** a price-quote basis rule) | Dec 2025 / Jan 2025 documents (earliest provided) | gold-guinea-january-2025-contract-onwards…pdf |
| GOLDPETAL | 1 g | 1 g | 999 | contracts from Apr 2025 document (earliest provided) | gold-petal-april-2025…pdf |

Normalization rule per spec: `price_per_fine_gram = quoted_price / (quote_grams × purity/1000)`. No special coin-premium quotation rule is present in the verified specs; the DDR conversion is a settlement-price construction, which is moot because no settlement prices exist in the corpus. The effective dates are the **earliest provided documents only** — provisional-verified status, listed in limitations.

## 5. Migration plan (Gates 1–7)

1. **Backend skeleton** — FastAPI modular monolith, pydantic-settings, SQLAlchemy 2 + Alembic, JSON logs, `/health/live` (no DB) and `/health/ready` (DB check). `DATABASE_URL` configurable; no PostgreSQL server/Docker exists on this machine → default local dev DB is SQLite via SQLAlchemy (portable schema; psycopg installed, PostgreSQL URL documented and supported), a documented deviation.
2. **Read-only ingestion** — manifest (rel path, SHA-256, size, detected format, class), signature sniffing, HTML-table parser, PDF registration + text-extract, classification & validation, staging rows with row-level reasons, idempotent import keyed by file-hash + row natural keys, ingestion report persisted; nothing is ever written under `GoldMcx_Data/`.
3. **Contract master + normalization** — verified effective-dated `contract_specs` seeded from §4, activity-only price normalization producing `PROVISIONAL` `normalized_prices` (method `activity_implied`), canonical six pairs.
4. **Analytics & scoring** — pair features (spread %, change, ratio), pair-specific robust-MAD calibration with cutoff isolation, deterministic scoring with full explainability payload.
5. **API layer** — all TRD §10 endpoints under `/api/v1` incl. admin-scoped ingestion, signals with disposition stages (decay anomalies vs. actionable), events (from source-extracted Guinea Tender-period change etc.), explicit validation errors (no silent pair fallback).
6. **Backtesting** — chronological walk-forward with costs/slippage model on provisional pair features, benchmark separation, run metadata; results labelled provisional.
7. **Frontend adapter** — `src/services/*` per TRD §11.1, `VITE_DATA_MODE=api|local|hybrid`, legacy alias mapping, local mode untouched by default; data-mode status surfaced.

## 6. Open limitations (recorded up-front)

1. **No OHLC/settlement/expiry/OI data exists in the supplied corpus** → expiry-window features and contract-specific expiry identity are structurally unavailable; expiry checks report UNSCORABLE rather than guessed.
2. No PostgreSQL server / Docker on this machine → SQLite local default (alembic migrations kept portable), dev provenance documented.
3. Contract specs: earliest effective documents only; earlier-period purity/quote rules (e.g., pre-2019 GOLDM 1 kg?) unverified → specs carry `VALIDATION_STATUS=PROVISIONAL` for pre-2019 dates.
4. Activity-implied prices are averages over all traded contracts of a symbol on a date — **not** one expiry's price; this is surfaced in every API response's `derivation_method`.
