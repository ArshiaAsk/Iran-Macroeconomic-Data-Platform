# Phase 4 Validation Report

**Status:** ✅ Complete — IMF and EIA validated; OPEC gate evaluated and closed
as blocked.
**Validation Date:** September 12, 2026
**Environment:** local workstation, `development` branch, Python 3.12, Poetry,
Playwright 1.62 (Chromium), Docker PostgreSQL 15 + TimescaleDB, sandboxed
network with escalated approval for outbound calls.

Every result below was produced in this environment; live-API claims say so
explicitly, and fixture-based results are labelled as such.

---

## Summary

| Area | Result |
|------|--------|
| Unit suite | **496 passed**, coverage **87.51%** (gate 80%) |
| Integration suite | **73 passed**, 3 live-skipped (World Bank + TGJU + IMF + EIA + DB) |
| `mypy src/` | clean (29 files) |
| `ruff check` / `ruff format --check` | clean |
| IMF | ✅ 42 unit + 16 integration; real live run (302 Silver / 404 Gold) |
| EIA | ✅ 48 unit + 12 integration; live schema/auth verified, live **run** pending a real API key |
| OPEC | ⛔ Blocked; not implemented (no code, fixtures, DAG, or config) |

---

## IMF validation (Task 10)

### Live API verification (2026-09-12)

| Property | Observed |
|----------|----------|
| Base / auth | `https://www.imf.org/external/datamapper/api/v1`, no auth |
| `/indicators` | 132 codes; all `"World Economic Outlook (April 2026)"`; unit/label metadata |
| Country path | **Ignored** — `/NGDP_RPCH/IRN` returns the same 229-country payload |
| `periods` parameter | **Ignored** — the full series is returned |
| Invalid code | HTTP **200**, only an `api` key, no `values` → treated as a retrieval error |
| Values | `values[""] = null` quirk present; numbers keyed by four-digit string years |
| Iran coverage | 1980–2031 (52) for `NGDP_RPCH`/`NGDPD`/`NGDPDPC`/`PCPIPCH`/`BCA_NGDPD`; 1990–2031 (42) for `LUR`; no nulls |
| Forecasts | Not labelled; classified against the vintage year (project convention) |

### End-to-end run (real API + dev database)

```bash
poetry run python -m src.connectors.imf
```

Result: `6/6 indicators ok`, **302 Silver rows**, **404 Gold rows**.

| Indicator | Coverage (Silver) | Silver | Levels | YoY |
|-----------|-------------------|-------:|-------:|----:|
| `NGDP_RPCH` | 1980–2031 | 52 | 52 | — |
| `PCPIPCH` | 1980–2031 | 52 | 52 | — |
| `NGDPD` | 1980–2031 | 52 | 52 | 51 |
| `NGDPDPC` | 1980–2031 | 52 | 52 | 51 |
| `LUR` | 1990–2031 | 42 | 42 | — |
| `BCA_NGDPD` | 1980–2031 | 52 | 52 | — |

Observed `observation_type` per 52-row series: `actual` 46, `estimate` 1,
`forecast` 5 (`LUR`: 36 / 1 / 5). Bronze `vintage = 2026`,
`forecast_through = 2031`. No chain-linking (`chain_linking_log` empty).

### Tests

- `tests/unit/connectors/test_imf.py` (20) + `test_imf_parser.py` (22) = **42 passed**.
- `tests/integration/test_imf_pipeline.py`: **15 passed**, 1 live-skipped —
  Bronze envelope, forecast retention/labelling, catalog coverage through 2031,
  Gold levels + opt-in YoY, hypertable, lineage, idempotent re-run.

---

## EIA validation (Task 11)

### Live API verification (2026-09-12)

| Property | Observed |
|----------|----------|
| Base / route | `https://api.eia.gov/v2/international/data/` |
| Auth | Missing key → HTTP **403 `API_KEY_MISSING`**; invalid → **403 `API_KEY_INVALID`** |
| Response | `response.total` and `value` are **strings**; `response.data` is the observation array |
| Facets | `facets[countryRegionId][]=IRN`, `productId=55|53`, `activityId=1` |
| Sorting | `sort[0][column]=period&sort[0][direction]=asc` returns 1993-01 first |
| Paging | `length`/`offset` honoured (`offset=200` returns the tail) |
| Date bounds | No `start` → 401 months back to 1993; `start=2024-01` → **29** rows |
| Rate limit | `DEMO_KEY` → HTTP 429, retried then surfaced as a run failure |
| Captured schema | `unitName="thousand barrels per day"`, `countryRegionName="Iran"`, `dataFlagId/Description` |

### Tests

- `tests/unit/connectors/test_eia.py` (29) + `test_eia_parser.py` (19) = **48 passed**.
  Covers string coercion, blank/null → NaN, non-numeric → `ParsingError`,
  month-end (incl. leap years), paging assembly, `total` string handling,
  unknown-facet empty series, missing/placeholder/invalid key, **403 not
  retried**, the credential-scrub regression, and provenance.
- `tests/integration/test_eia_pipeline.py`: **12 passed** — Bronze envelope +
  paging metadata, key non-leakage, monthly Silver, prior-year-month YoY,
  hypertable, catalog coverage, idempotent re-run, and missing-key abort with
  zero rows written.

### Live behaviour verified through the CLI

```bash
poetry run python -m src.connectors.eia --dry-run          # placeholder key
# → "EIA API key is not configured …" ; exit code 1 ; nothing written

EIA_API_KEY=DEMO_KEY poetry run python -m src.connectors.eia --dry-run
# → HTTP 429 retried 3× then aborted cleanly, exit 1, key shown as api_key=***
```

**Not done:** a successful live EIA ingestion. No real `EIA_API_KEY` exists in
this environment and `DEMO_KEY` is rate-limited. Coverage for EIA is
fixture-observed (2024-01 … 2026-05) until a key is supplied.

---

## OPEC basket gate (Task 12/13) — **BLOCKED, not implemented**

**Decision:** the OPEC Reference Basket is **not ingested**. No connector,
parser, fixture, DAG, or configuration was added, and no browser-automation
workaround was built.

### Evidence

| Target | Result (2026-09-12) |
|--------|---------------------|
| `GET …/OPEC_Basket_Daily.xlsx` | HTTP 200 but `Content-Type: text/html`, 245,600 bytes, magic `<htm`, not a zip, `challenge-platform` present — a Cloudflare challenge page, not a workbook (reproduced twice) |
| `GET …/OPEC_Basket_Daily.csv` | Same HTML challenge page |
| `GET https://asb.opec.org/data/CSVData.php` | `ConnectionResetError: [Errno 104]` |
| `GET …/opec_web/en/data_graphs/40.htm` | Connection reset; in a browser it redirects to the homepage |
| `GET https://www.opec.org/robots.txt` | **HTTP 403** Cloudflare block page (`server: cloudflare`, `cf-ray`) |
| `GET …/basket/basketDay.json` (plain client) | **HTTP 403** Cloudflare block page (5,779-byte HTML) |
| `…/basketMonth.json`, `…/basketYear.json` (plain client) | HTTP 403 |
| `…/opec-reference-basket-orb.html` (headless Chromium) | HTTP 200 but no `<table>` and no price/unit text; chart rendered client-side |
| Network capture of that page (headless Chromium) | The page fetches `/basket/basketDay.json` and receives **HTTP 200 `application/json`**, ~177 KB, `[[Date.UTC(2003,0,2),30.05], …]` — daily values since 2003 |

### Why this is still blocked

A real browser reaches the data only because Cloudflare lets browser traffic
through while returning **403 Forbidden** — an explicit access denial — to every
programmatic client. Fetching the endpoint from Playwright would be a bypass of
that control, not a supported data path, and it would be fragile (dependent on
winning the same bot-management heuristics every scheduled run). The checkpoint
rules this out, and `AGENTS.md` requires respecting `robots.txt`, which here is
itself denied to automated clients.

### Consequences

- No OPEC indicator appears in the catalog; revisit only if a stable, explicitly
  accessible source appears (e.g. an official API or a publication that permits
  programmatic download).
- Task 13's design (daily Silver + month-end Gold via `src/etl/frequency.py`)
  remains valid for that future attempt.
- IMF and EIA, the committed Phase 4 deliverables, do not depend on OPEC.

---

## Regression and quality gates

| Command | Result |
|---------|--------|
| `poetry run pytest -m "not integration"` | **496 passed**, coverage **87.51%** |
| `poetry run pytest tests/integration -m integration` | **73 passed**, 3 live-skipped |
| `poetry run mypy src/` | no issues (29 files) |
| `poetry run ruff check src tests` | clean |
| `poetry run ruff format --check src tests` | clean |

World Bank and TGJU behaviour is unchanged: `run_world_bank_pipeline` is a thin
wrapper over the generic runner and its integration suite still passes, and the
TGJU scraper keeps its own runner. The only data migration is the one-off TGJU
derived-id cleanup (`20260912_1256_normalise_tgju_derived_ids`).

---

## Known issues / technical debt

1. **OPEC deferred** (above) — the single unfilled Phase 4 data source.
2. **EIA live run unverified** — no real API key in this environment.
3. **`build_spec()` returns `Any`** in `imf.py` / `eia.py` because of the local
   import that mirrors `world_bank.py`'s cycle-avoidance pattern. Functionally
   fine; would benefit from a `TYPE_CHECKING` annotation.
4. **IMF catalog label whitespace** — the API label for `NGDPDPC` ends in a
   newline, so the catalog name carries it. Cosmetic; a one-line `.strip()` in
   `discover()` would fix it.
5. **`src/etl/frequency.py` is currently unused by any connector** (it was built
   for the deferred OPEC path). It is tested and available for future daily
   sources.
