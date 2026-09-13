# Phase 4 Implementation Report

**Status:** ✅ Complete for the committed scope — IMF and EIA connectors
implemented; OPEC evaluated and deferred (source blocked).
**Completed:** September 12, 2026
**Plan:** [phase-4-additional-api-connectors.md](../plans/phase-4-additional-api-connectors.md)

---

## Executive Summary

Phase 4 adds two API connectors — IMF DataMapper (annual, with forecasts) and
EIA Open Data v2 (monthly energy production) — on top of a generic pipeline
runner refactor, and makes year-over-year derivation frequency-aware. The OPEC
basket track was gated, evaluated against the live source, and **deferred**
because OPEC blocks programmatic access (Cloudflare); no OPEC code or
configuration was added.

The implementation follows the World Bank reference connector: injected
`http_session` / `RetryPolicy` / `RateLimiter`, a separate pure parser module,
`fetch_series()` returning a result object with `raw_envelope` / `request_url` /
`http_status_code`, `discover()` describing indicators, and `main()` delegating
to the shared runner. Unit tests run with no network and integration tests run
with no live HTTP (fixtures + real Docker PostgreSQL).

### What was built

| Component | Status | Tests |
|-----------|--------|-------|
| Generic pipeline runner (`SourceSpec`, `FetchResult`, `run_pipeline`) | ✅ Complete | 7 unit |
| Shared period helpers (`src/utils/periods.py`) | ✅ Complete | 21 unit |
| Frequency utilities (`src/etl/frequency.py`) | ✅ Complete | 8 unit |
| Forecast-aware Silver + frequency-aware YoY | ✅ Complete | in ETL suites |
| IMF connector + parser | ✅ Complete | 42 unit + 16 integration |
| EIA connector + parser | ✅ Complete | 48 unit + 12 integration |
| OPEC basket | ⛔ Deferred (blocked) | — |
| Documentation (this phase) | ✅ Complete | — |

---

## Architecture changes

### 1. Generic pipeline runner (`src/etl/pipeline.py`)

The runner was World Bank–specific. It is now driven by a `SourceSpec` +
`SeriesConnector` protocol pair, with `run_world_bank_pipeline` kept as a thin
wrapper (zero behaviour change for World Bank) and `run_cli` accepting any
connector + spec. New API sources add a connector and a spec — never a new
runner.

- `FetchResult` (runtime-checkable protocol, **read-only properties**) is what a
  connector hands back for one indicator.
- `IndicatorDerivation` / `SourceSpec` carry source name/type, frequency,
  derived-series namespace, per-indicator derivation overrides, forecast
  support, and the Bronze-row parser.
- `run_pipeline(connector, spec, indicators, dry_run)` connects, discovers,
  seeds the catalog, and runs one session per indicator. It does **not** close
  the connector — the caller owns lifecycle.
- `run_cli(connector=..., spec=...)` is the shared CLI entry point; with no
  connector it still runs World Bank exactly as before.

### 2. Shared period helpers (`src/utils/periods.py`)

`annual_period_end`, `month_period_end`, `parse_period`, and `year_earlier`.
`year_earlier` snaps month-end inputs to the prior month's end, which is what
makes monthly YoY exact across leap years (Feb 28 2025 → Feb 29 2024).

### 3. Frequency-aware YoY (`src/etl/gold.py`)

`_growth_records` now looks up the **exact same period one year earlier** rather
than taking a positional lag. Annual behaviour is unchanged; monthly series no
longer silently publish MoM as YoY, and a missing prior-year period yields no
rate instead of a fabricated one.

### 4. Forecast-aware Silver (`src/etl/silver.py`, `src/utils/validation.py`)

`validate_date_range` / `validate_data_quality` gained `allow_future` / `now`.
`bronze_to_silver(..., allow_future=True)` keeps intentional future periods
(IMF WEO forecasts), counts them as `forecast_records`, and records
`observation_type` in the Silver metadata. Non-forecast sources keep the old
reject-future behaviour.

### 5. Derived-id idempotency + one-off cleanup migration

`_namespaced` keeps derived ids from double-prefixing a namespaced source
(`TGJU.TGJU.…` → `TGJU.…`). Migration
`alembic/versions/20260912_1256_normalise_tgju_derived_ids.py` deletes the
already-published double-prefixed TGJU Gold rows (no-op downgrade).

### 6. Frequency conversion (`src/etl/frequency.py`)

`to_month_end` / `aggregate_to_monthly` implement the AGENTS.md
end-of-month rule: last observation per month, stamped at month end, no
forward-fill. Built for the (deferred) OPEC daily→monthly path and available for
future daily sources.

---

## Sources

### IMF DataMapper (`src/connectors/imf.py`, `imf_parser.py`)

- 6 WEO indicators for Iran: `NGDP_RPCH`, `PCPIPCH`, `NGDPD`, `NGDPDPC`, `LUR`,
  `BCA_NGDPD`.
- The API ignores the country path and the `periods` parameter, so the connector
  fetches the full payload and selects `IRN` client-side, keeping the whole
  response in `raw_response` for audit.
- Vintage parsed from `source` (`"World Economic Outlook (April 2026)"`); the
  actual/estimate/forecast label is derived against the vintage year and
  **documented as a project convention**, not an IMF field.
- Forecast rows are future-dated and retained through Silver and Gold
  (`supports_forecasts=True`).
- Rate indicators get no derived series; `NGDPD` / `NGDPDPC` get
  `IMF.<id>.YOY`.
- Observed run (2026-09-12): 302 Silver rows, 404 Gold rows (1980–2031; `LUR`
  from 1990).

### EIA Open Data v2 (`src/connectors/eia.py`, `eia_parser.py`)

- 2 monthly indicators: `EIA.IRN.CRUDE_PRODUCTION` (`productId=55`) and
  `EIA.IRN.TOTAL_LIQUIDS` (`productId=53`), both `activityId=1 ("Production")`.
- Facet filtering, `length`/`offset` paging until the string `response.total` is
  reached, explicit ascending sort, and a default window (`start=2024-01`).
- API key from `EIA_API_KEY`; a missing/placeholder/invalid key aborts the run
  once with an actionable `PlatformConnectionError` (403 is not retried).
- The key is scrubbed from error/retry text and never appears in Bronze
  `request_url` or metadata.
- Derived `EIA.<id>.YOY` is a genuine prior-year month comparison.

### OPEC basket — deferred

The source is blocked: `.xlsx`/`.csv` downloads return a Cloudflare challenge
page, direct JSON endpoints return HTTP 403, and `robots.txt` itself is 403. A
browser session can reach `/basket/basketDay.json`, but only by bypassing the
bot block, which the checkpoint explicitly rules out. No OPEC code, parser,
fixture, DAG, or configuration was added. See
[VALIDATION.md](VALIDATION.md) for evidence.

---

## Deviations from the plan

| Plan | Actual | Why |
|------|--------|-----|
| EIA fixtures named `crude_production_page1/2.json`, `empty_facets.json`, `missing_key_error.json` | `CRUDE_PRODUCTION_normal.json`, `TOTAL_LIQUIDS_normal.json`, `unknown_facet.json`, `API_KEY_MISSING.json`, `API_KEY_INVALID.json` | Paging is simulated server-side from one payload; the auth fixtures name the two real 403 codes |
| EIA config had no `start`/`end` | Added `start` (default `2024-01`) / `end` | The plan's data flow and expected ≈29 rows require a bound; unbounded the API returns 401 months back to 1993 |
| OPEC parser/scraper + fixtures to ship | Nothing shipped | The checkpoint instruction forbids working around Cloudflare or shipping a fragile path |
| Task 12 added `opec_base_url` config | Skipped | Dead configuration for a source that is not ingested |
| `build_spec()` returns `Any` (IMF, EIA) | Kept | Local import mirrors `world_bank.py`'s cycle-avoidance pattern; minor typing debt |

---

## Files added / changed

**Added**

- `src/connectors/imf.py`, `src/connectors/imf_parser.py`
- `src/connectors/eia.py`, `src/connectors/eia_parser.py`
- `src/utils/periods.py`, `src/etl/frequency.py`
- `alembic/versions/20260912_1256_normalise_tgju_derived_ids.py`
- `tests/fixtures/imf/`, `tests/fixtures/eia/`
- `tests/unit/connectors/test_imf*.py`, `test_eia*.py`
- `tests/unit/utils/test_periods.py`, `tests/unit/etl/test_frequency.py`
- `tests/integration/test_imf_pipeline.py`, `test_eia_pipeline.py`
- `tests/unit/etl/test_pipeline.py`
- `docs/phase-4/*`

**Changed**

- `src/etl/pipeline.py`, `src/etl/silver.py`, `src/etl/gold.py`,
  `src/connectors/world_bank.py`, `src/utils/validation.py`
- `tests/conftest.py`, `tests/unit/etl/test_gold.py`, `test_silver.py`,
  `tests/unit/utils/test_validation.py`
- `README.md`, `AGENTS.md`, `.env.example`, `docs/phase-2/data_dictionary.md`
