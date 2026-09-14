# Phase 6 — Market & Survey Connectors

**Status:** 🟢 Task 1 (reconnaissance / dependency gate) **approved 2026-09-13** —
Task 2 (optional extras + config) in progress. Task 3+ not started.
**Date:** 2026-09-13
**Environment:** local workstation, Python 3.12.3, Poetry 2.4.1; packages
installed in a scratch venv (`/tmp/p6recon`) with escalated network access.
**Plan:** `docs/plans/phase-6-market-survey-connectors.md`

This directory holds the Phase 6 gate record, implementation notes, and
validation report (`IMPLEMENTATION.md` / `VALIDATION.md` land in Task 10).

---

## Approved decisions (2026-09-13)

Task 1 is approved with the following scope decisions, which are binding for
Tasks 2+:

### TSETMC
- **OPEN: `TSETMC.TEDPIX` only** — daily level series from `Get_CWI_History`.
- Include the existing daily derivations **`RET1D`** and **`MA30`**, plus the
  planned month-end **`.ME`** series.
- **DEFER `Trading Value` and `Market P/E`.** Task 1 established that
  `finpy-tse` provides no reliable *historical* version of either indicator.
  They must **not** be invented or reconstructed from current-day snapshots.
- **DEFER market capitalization** unless a reliable historical source is
  actually available (none was found).

### HBSIR
- **OPEN: weighted Gini** and **weighted income decile shares**.
- **Poverty rate is OPEN only as an explicitly documented *relative* poverty
  measure.** Initial configurable definition: **`50% × weighted median income`
  (household-weighted)**. It must **not** be described as the official Iranian
  poverty line; the methodology (basis, weighting, threshold) must be recorded
  in the indicator metadata/documentation.
- **Weights are mandatory** — fail loudly (`ParsingError`) if unavailable.
- **Preserve the Jalali survey year** in metadata and convert the observation
  timestamp to the correct **Gregorian Iranian year-end**, handling Esfand
  29/30 (leap years) rather than hardcoding `12-29`.

---

## Gate summary

| Source | Package | Verdict | One-line reason |
|--------|---------|---------|-----------------|
| **TSETMC** | `finpy-tse==1.2.10` | ✅ **OPEN** (for TEDPIX) | Live daily TEDPIX history 2008-12-04 → today, no auth; but the package exposes **no market P/E and no historical aggregate trading value** |
| **HBSIR** | `hbsir==0.6.6` (+`bssir==0.6.8`) | ✅ **OPEN** | Real microdata loads offline after auto-download; income/expenditure/weights present; 1369–1403 coverage |

Both packages install and import cleanly on Python 3.12 and are pure-python
(`py3-none-any`) with permissive licenses. The gate passes for **both sources**,
with a **scope adjustment for TSETMC** described below.

---

## TSETMC — ✅ OPEN, with a scope change

### Installability / compatibility
- `pip install finpy-tse` → **1.2.10**, pure-python wheel, imports on 3.12. No
  `Requires-Python`, no compiled deps. ✅
- License **BSD 3-clause**; last release **2024-04-24**; no PyPI project URL. No
  `__version__` attribute (use `importlib.metadata.version("finpy-tse")`).
  Maintenance is stalled but the endpoints are stable (verified live).

### Evidence (smallest real reads)
- `finpy_tse.Get_CWI_History(ignore_date=True, just_adj_close=True)` →
  **4,283 sessions, 1387-09-14 (2008-12-04) → 1405-06-22 (2026-09-13)**, one
  row per trading day, index close level. No browser, no credentials.
- Raw `cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957` → HTTP 200,
  fields `dEven`, `xNivInuClMresIbs`, `xNivInuPbMresIbs`, `xNivInuPhMresIbs`.
- Market-holiday gaps are **absent, not filled** (two-week window → 9 rows).
- Fixtures: `tests/fixtures/tsetmc/` + `SOURCES.md` + `_capture.json`.

### Findings that change Task 4
1. **TEDPIX = `Get_CWI_History`** ("شاخص کل", `insCode 32097828799138957`).
   Index close is returned in a column mislabelled `"Adj Close"`. There is no
   adjusted/unadjusted choice for the index; record `insCode` + package version
   in metadata and treat level jumps as data, not a splice.
2. **Market P/E is not available** anywhere in the package (`Get_MarketWatch`
   has per-symbol `EPS`/`Close` only) nor in the cdn endpoints probed
   (`MarketData/GetMarketOverview/{1,2,3}`, `MarketWatchInit.aspx`).
3. **Historical aggregate trading value is not available.** `Get_MarketWatch`
   and `GetMarketOverview` return **current-day** snapshots (per-symbol value /
   market cap; aggregate `marketActivityQTotTran`), never history — so there is
   no backfill for a "retail trading value" series.
4. **Market cap / P/E are therefore out of the package-only MVP**, exactly the
   plan's stated fallback ("if not, drop it from the MVP"), now extended to P/E.

### Verdict
**OPEN for the TEDPIX level series** (daily + month-end), which delivers the
headline PRD demo (TEDPIX vs monthly CPI/FX). **Trading value and market P/E
move to DEFER** unless/until approved for a follow-up that either accumulates
`MarketOverview` daily going forward or derives a market P/E from a full symbol
snapshot — both are outside "wrap the package" and need a review decision.

### Recommended next step
Proceed to Task 2/3, but scope Task 4's indicator registry to
**`TSETMC.TEDPIX`** for the MVP (plus the planned `RET1D`/`MA30`/`.ME`
derivations). Flag the trading-value / P-E gap for the reviewer; if they want
them, plan a small, documented cdn `MarketOverview` path (forward-only, no
backfill) rather than silently dropping the PRD indicators.

---

## HBSIR — ✅ OPEN

### Installability / compatibility
- `pip install hbsir` → **0.6.6** + `bssir 0.6.8`, pure-python, imports on 3.12.
  `Requires-Python >=3.10` (fits 3.11–3.12). ✅
- License **MIT** (both), GitHub `Iran-Open-Data/HBSIR`, actively maintained
  (releases through 2025-12). `hbsir.__version__` is present.

### Evidence (smallest real reads)
- `hbsir.load_table("Weight", 1400)` → ✅ 37,988 rows (`Year, ID, Weight`); the
  package auto-downloaded cleaned Parquet from the Arvan S3 mirror.
- `Total_Income` (`Year, ID, Income`) and `Total_Expenditure`
  (`Gross_Expenditure`, `Net_Expenditure`) load for **1369…1403** (35 years;
  probed 1369/1385/1390/1395/1400/1403).
- A real household-weighted merge reproduces a sane trend: **Gini** 1390=0.349,
  1395=0.377, 1400=0.370, 1403=0.345; decile shares sum to ~100; weighted
  household counts 21 M → 28 M.
- Fixtures: `tests/fixtures/hbsir/` + `SOURCES.md` + `_manifest.json`.

### Findings that shape Task 5
1. `hbsir` is a **loader + metadata package, not an HTTP client**; the connector
   injects a loader and works offline from `Data/HBSIR/4_cleaned/` after the
   first download. Bronze strategy (persist the annual input extract + manifest,
   not raw microdata) fits the plan.
2. **Weights are essential and available** (`Weight` table; the package derives
   them from province shares + census counts). The parser must require them.
3. The package provides weighted quantile/decile helpers but **no Gini and no
   poverty line** — consistent with the plan's "derive in-platform".
4. Poverty line must be **explicit**: no official خط فقر in the package.
   Recommend a configurable relative line (default 50% × weighted median
   household income) recorded in metadata; official SCI line is a follow-up.
5. Survey years are **Jalali**; compute the true Iranian year-end (Esfand 29 or
   30) rather than hardcoding 12-29, and keep the Jalali year in metadata.

### Verdict
**OPEN.** All required inputs for Gini / poverty / income-decile shares are
present, weighted, and cover 10+ survey years.

### Recommended next step
Proceed to Task 5 with `HBSIR.GINI`, `HBSIR.POVERTY.RATE`,
`HBSIR.INCOME.DECILE.D1..D10`, an injected loader, and a relative poverty line
in config/metadata.

---

## Deviations from the plan (recorded, not silent)

- **TSETMC indicator scope.** The plan assumed the package could supply
  TEDPIX, trading value, and market P/E. Reconnaissance shows only TEDPIX is
  package-supported; the other two have no historical source in `finpy-tse` or
  the probed cdn endpoints. **Approved:** the MVP narrows to TEDPIX; trading
  value / market P/E / market cap are deferred.
- **Bronze for TSETMC.** The plan stores "the package payload" in Bronze; the
  package returns a processed DataFrame and discards the raw envelope. The
  raw `indexB2` JSON is captured here so the connector can persist *both* the
  raw payload (retrievable via the same `insCode`) and the normalized frame.
- **No new deps beyond the plan.** Both packages were validated in a scratch
  venv; Task 2 adds them to `pyproject.toml` as **optional extras** (pinned to
  the Task 1 versions) so the default install and unit suite stay package-free.

## Environment limitations
- Network is sandboxed; installs and live reads required escalated approval.
  The gate evidence above was gathered under that approval. HBSIR downloads
  (~tens of MB per year) land in the scratch venv's `Data/`, not in the repo.

## Gate decision — RESOLVED (2026-09-13)

All three open questions were approved as recorded in **Approved decisions**
above:

1. TSETMC MVP = **TEDPIX only**; trading value and market P/E **deferred** (no
   current-day reconstruction). Market cap deferred.
2. HBSIR poverty line = **relative `50% × weighted median income`**, kept
   configurable and documented as *not* the official Iranian line.
3. TSETMC Bronze stores the **raw `indexB2` payload + normalized frame**; HBSIR
   preserves the Jalali year in metadata with a correct Gregorian year-end.
