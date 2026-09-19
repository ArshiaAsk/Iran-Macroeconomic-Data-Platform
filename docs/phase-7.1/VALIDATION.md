# Phase 7.1 Validation Report

**Status:** ✅ Accepted (Tasks 1–28) — Task 28 analyst acceptance pass recorded
2026-09-19 against a populated local database.
**Plan:** [phase-7.1-dashboard-refresh.md](../plans/phase-7.1-dashboard-refresh.md)
**Runbook:** [README.md](README.md) · **Implementation:** [IMPLEMENTATION.md](IMPLEMENTATION.md)

This report records the commands and outcomes actually observed for the
implementation that shipped. It distinguishes **verified in this run** from
**not automated in this run**.

**Revision note (2026-09-19, Task 28):** an earlier revision of this report
recorded Tasks 27 (extended test suite) and 28 (analyst acceptance pass) as
outstanding. That was stale: the final commit
(`35a3e92 feat: complete phase 7.1 dashboard refresh`) landed the Task 27 test
suite — `tests/unit/dashboard/test_literal_guard.py` (the AST literal guard),
the router-based `app_smoke.py`, the domain-ownership assertions and the
corrected export-header integration assertion. Both tasks are now executed and
recorded below; the stale "Remaining Gaps" entries have been removed.

## Validated Environment

| Component | Version |
|-----------|---------|
| Poetry | 2.4.1 |
| Python | 3.12.3 |
| Streamlit | 1.61.1 |
| Plotly | 6.x |
| Kaleido | 1.x |
| PostgreSQL + TimescaleDB | `timescale/timescaledb:latest-pg15` (healthy) |
| pytest | 7.4.4 |

---

## Wave-0 Spike Outcome

Full evidence in [wave-0-spike.md](wave-0-spike.md). Summary of the approved
decisions and how they landed:

- `st.navigation` **approved** and implemented — required for Persian sidebar
  labels, grouping, ordering and default-page control.
- The page registry is **plain data + an in-app builder** (`PageSpec` rows in
  `dashboard/navigation.py`, `st.Page` objects built inside `app.py`), consumed
  by both `st.navigation` and the data-level tests. `url_path` is left unset.
- The Streamlit floor was bumped to `^1.36` with a **`poetry lock` refresh
  only** — no package version changed (the lock already resolved 1.61.1).
- `AppTest` migration was **partially supported**: `switch_page` renders a page
  but bypasses the router, so per-page nav/ownership assertions are made against
  the registry. Task 27 migrated the smoke harness onto the router entrypoint
  (`AppTest.from_file(app).switch_page(...)`), keeping the direct-file path as a
  fallback; the switch_page bypass remains why ownership is asserted at the
  registry level.

---

## Level 1: Static / Style

```bash
poetry run ruff check dashboard src tests
poetry run ruff format --check dashboard src tests
poetry run mypy src dashboard
```

✅ **Result (observed 2026-09-19, re-run in Task 28):**

- `ruff check` — no errors.
- `ruff format --check` — `141 files already formatted`.
- `mypy src dashboard` — `Success: no issues found in 63 source files`.

**Quality-gate decision:** `mypy src dashboard` was run and passes.
`make typecheck` was **not** widened (it still runs `mypy src/` only), and
`--cov=src` is unchanged, so dashboard code is linted and type-checked
explicitly but not measured by the project coverage gate. This closes Open
Item 7 explicitly rather than leaving the gate ambiguous.

---

## Level 2: Dashboard Unit Tests

```bash
poetry run pytest tests/unit/dashboard -q --no-cov
```

✅ **Result:** **340 passed** across 14 test files, including repository
shaping, derived/orphan discovery, derived-series labels, navigation/domain
ownership, Persian string catalog and label coverage, formatting (digits,
Jalali, Tehran round-trip), filters (Jalali presets), RTL direction, chart
scaling, tables, exports, quality, the **AST literal guard**
(`test_literal_guard.py`) and offline `AppTest` smoke tests for every page.

## Level 2b: Project-Wide Unit Tests

```bash
poetry run pytest tests/unit -q
```

✅ **Result:** **1,157 passed, 3 skipped**, coverage **89.22%** (gate 80%).

The three skips are live-source tests gated behind `RUN_LIVE_API_TESTS=1`.
`tests/unit/etl/test_gold.py` — the 10 failures recorded in the Phase 7 report —
now passes.

---

## Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run alembic check
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
```

✅ **Result (observed 2026-09-19, Task 28):** **131 passed, 4 skipped, 0 failed**
(529 s). `alembic upgrade head` was a no-op and `alembic check` reported
`No new upgrade operations detected` (no model/database drift).

The four skips are live external-source tests gated behind
`RUN_LIVE_API_TESTS=1`.

The **stale export-header failure recorded in the previous revision of this
report is resolved**: `tests/integration/test_dashboard_repository.py::test_selected_export_contains_exact_database_rows`
now asserts the localized header via `t("table.chain_linking_confidence")`
instead of the raw English column name, and passes. The 18 dashboard-repository
integration tests pass on their own in 4 s.


---

## Level 4: Feature-Specific Validation

### Boundary check

```bash
git diff --name-only origin/development...HEAD -- src/            # expect 0
git diff --name-only origin/development...HEAD -- alembic/versions/  # expect 0
```

✅ **Result:** 0 files under `src/` and 0 under `alembic/versions/`. The phase
changed only `dashboard/` (20 files), `tests/` (24 files), `pyproject.toml` and
`.streamlit/config.toml`.

### Headless launch

```bash
poetry run streamlit run dashboard/app.py --server.headless true --server.port 8599
```

✅ **Result:** Streamlit started and reported `Uvicorn server started on :::8599`
and `Local URL: http://localhost:8599`. The run was stopped by timeout.

### Jalali round-trip

Covered by unit tests (`tests/unit/dashboard/test_formatting.py`,
`test_filters.py`), including an evening-UTC instant: a Jalali day resolves to
inclusive UTC bounds that round-trip back to the same Jalali day, and stored
Gregorian values and query semantics are unchanged.

---

## Level 5: Data Refresh & Task 28 Analyst Acceptance

### Environment (populated local database, 2026-09-19)

Database `iran_macro_db` on `timescale/timescaledb:latest-pg15` (healthy), with
all seven source pipelines already loaded. Task 28 did **not** re-run the live
connectors (the plan's Level 5 `python -m src.connectors.*` commands hit
external, rate-limited sources); it **re-derived every count from the populated
database** and rendered every page against it.

### Actual counts (re-derived, not copied from the plan)

| Metric | Actual |
|---|---|
| Catalog rows | **54** (50 active + 4 inactive SCI base-year segments) |
| Active domains | **9** (energy 3, fx 1, gdp 8, gold 2, inflation 15, labor 1, market 1, trade 4, welfare 15) |
| Active sources | **7** (world_bank 12, sci 14, imf 6, hbsir 12, eia 2, tgju 3, tsetmc 1) |
| Gold observations | **20,074** rows across **82** distinct series |
| — base series | **50** (all have a catalog row) |
| — derived series | **32** (World Bank 12, SCI 13, TSETMC 3, EIA 2, IMF 2) |
| — genuine orphans | **0** |
| Silver observations | **8,446** (tsetmc 4,286; sci 2,649; world_bank 758; hbsir 384; imf 302; eia 58; tgju 9) |
| TSETMC sessions | TEDPIX **4,286**; RET1D 4,285; MA30 4,257; `.ME` 214 month-ends |
| Freshness (latest run) | tsetmc 2026-09-17, hbsir 2026-09-15, eia/imf/sci 2026-09-13, tgju/world_bank 2026-09-11 — all `success` |

**Derived series: actual 32, not the plan's ≈38.** The plan's figure was
indicative; the real run produces 32 (SCI contributes 13 = 3 canonical + 10
decile `YOY`).

### Page-by-page render (real DB, no repository monkeypatch)

All ten registry pages were rendered through `dashboard/app.py` +
`st.switch_page` against the populated database with
`streamlit.testing.v1.AppTest`:

| Page | Exceptions | Title (Persian) | Notes |
|---|---|---|---|
| Overview | 0 | مرور کلی | 6 metrics; forecasts-indistinguishable warning; 2 tables |
| Inflation | 0 | تورم | decile + canonical + chain-linking + generic sections; 4 charts |
| GDP | 0 | تولید ناخالص داخلی و اقتصاد | derived toggle observable (66→131 rows) |
| Trade & Energy | 0 | تجارت و انرژی | no welfare content; empty-selection info by default |
| FX & Gold | 0 | ارز و طلا | one title + TGJU snapshot warning |
| Welfare & Survey | 0 | رفاه و آمارگیری خانوار | Gini/poverty + decile + survey-year + context sections |
| Market | 0 | بازار سرمایه | 4 panels (level, MA30, RET1D, `.ME`); 4,286-session metric; **no** false missing-period warning |
| Labor | 0 | بازار کار | single-observation warning; one chart |
| Correlation | 0 | مقایسه و همبستگی | requires ≥2 selected; guardrail warning verified |
| Catalog | 0 | فهرست داده‌ها | search + inactive toggle verified |

**Total exceptions across all ten pages: 0.**

### Verified behaviours

- **Navigation & ownership.** 10 pages in 2 groups; the registry owns the 9
  active domains exactly once; `economy` is unclaimed; the database's 9 active
  domains match the registry exactly.
- **Persian labels.** Every page title, subheader, warning, info and metric
  renders in Persian.
- **Jalali display.** The filter range echo shows Jalali labels beside the
  Gregorian UTC bounds (e.g. `۱۰ دی ۱۳۳۹ تا ۱۰ دی ۱۴۱۰ — … 1960-12-30 تا 2031-12-31`).
- **Chart modes.** The per-indicator facet default renders; the decile section
  uses small multiples; the chart-mode selectbox is present.
- **Observations tables.** Capped preview at 500 rows with a Persian truncation
  notice (Market: «۵۰۰ ردیف از ۴٬۲۸۶ ردیف»).
- **Exports.** CSV carries the UTF-8 BOM and Persian headers including
  `تاریخ شمسی` (Jalali) and `اطمینان زنجیره‌سازی`, with the ISO-8601 Gregorian
  `timestamp` retained; Excel opens as a PK zip with the RTL sheet flag; HTML
  (4,399 B), PNG (`\x89PNG`, 21,645 B) and SVG (`<svg…`, 7,009 B) render on
  demand with the installed Chromium (`/usr/bin/google-chrome`). With
  `DASHBOARD_CHROME_PATH` set to a bogus path the PNG/SVG buttons are
  **disabled** and a Persian caption explains why, with no exception.
- **Catalog search.** `inflation` → 15 matches; Persian `تورم` → 15 matches;
  the inactive-segment toggle → 54 rows.
- **Chain-linking transparency.** The section renders the provenance table and
  chart; `SCI.CPI.URBAN` and its `.YOY` display `is_chain_linked` with confidence
  `0.9985` and a stored `original_value` (12 of the 240 `.YOY` rows carry a null
  `original_value` — an ETL data nuance, displayed as stored).
- **Correlation guardrails.** Selecting two zero-overlap series
  (`HBSIR.GINI` ↔ `NY.GDP.MKTP.CD`) raises the Persian low-overlap warning
  («برای ۱ جفت شاخص … کمتر از حداقل ۳ …»); mixed frequencies raise their own
  warning; the exact-join caption and the join-count/overlap tables render.
- **Freshness indicators.** Seven sources with localized headers, Tehran/Jalali
  collection timestamps, and fresh/stale verdicts (tgju and tsetmc read `کهنه`
  against their daily cadence).
- **Derived-series exposure.** The «Include derived» toggle is observable
  (Inflation and GDP generic tables 66→131 rows) and derived rows inherit their
  parent's source (`SCI.CPI.URBAN.YOY` → source `sci`).

### Level 6: Quality gates

```bash
make check
```

✅ **Result:** `ruff format` (no-op) + `ruff check` + `mypy src/` +
`pytest -m "not integration"` → **1,157 passed, 3 skipped, 135 deselected**,
coverage **89.22%**. The working tree was unchanged afterwards.

---

## Data Validation Checks

✅ **Verified by the unit and integration suites and by code review:**

- Dashboard observations come only from `gold.gold_analytical`; Silver is never
  read for analytical values.
- Derived and orphan Gold rows survive the LEFT JOIN; derived rows inherit their
  parent's `name`/`source_name`/`source_url`; a genuine orphan keeps `NULL`
  provenance and is flagged by `has_catalog_metadata` rather than dropped.
- Derivedness is read from `record_metadata["derived_from"]`, never from an id.
- Timestamps remain timezone-aware UTC; date filters are applied in SQL.
- No interpolation, forward-fill, resampling or normalization is introduced.
- Chain-linking values are displayed as stored (linked value, original value,
  confidence, `record_metadata`); nothing is recomputed.
- Correlation uses exact-timestamp matches only; low-overlap cells are masked.
- Catalog search normalizes the needle only; stored data is never rewritten.

---

## Accepted Deviations

1. **Cache TTL / refresh control not shipped.** The plan's Task 7(d) required a
   `ttl=` on every `st.cache_data` wrapper plus `clear_dashboard_cache()`, and
   the acceptance criteria require a pipeline run to be visible without an app
   restart. Neither is implemented: `dashboard/queries.py` uses
   `@st.cache_data(show_spinner=False)` with no TTL, and there is no refresh
   control. A pipeline run needs an app restart. Documented as a known
   limitation in the runbook.
2. **`series_kind` uses `base`/`derived`, not `level`/`derived`** as the plan
   wording suggested.
3. **`build_coverage_chart` deleted** (the plan allowed wire-or-delete); the
   Overview uses metrics and tables instead.
4. **Forecast labeling deferred** with an in-UI disclaimer; IMF forecast rows are
   **indistinguishable** from actuals in the UI (Gold carries no
   `observation_type`).
5. **Dataframe grid stays LTR**; only headers/digits/dates are localized.
6. **`make typecheck` not widened** (see the quality-gate decision above).

---

## Remaining Gaps & Observations

- **Task 27 (extended test suite) is executed.** The AST literal guard
  (`tests/unit/dashboard/test_literal_guard.py`), the router-based
  `app_smoke.py`, the domain-ownership assertions and the corrected export-header
  integration test all landed in `35a3e92` and pass. The earlier revision of this
  report recorded them as outstanding; that was stale.
- **Task 28 (analyst acceptance pass) is executed** (Level 5, above): every page
  was rendered against the populated database, every count was re-derived, and
  the behaviours were verified programmatically. The plan's manual
  `make dashboard` browser click-through is the one step that remains a
  human-in-the-loop activity; the equivalent render/interaction checks were
  performed through `AppTest` against the real database.
- **Cache TTL / refresh control** (accepted deviation 1) remains an open
  acceptance criterion: a pipeline run still needs an app restart.
- **Overview "Gold observations" metric is catalog-scoped (observation, not
  defect).** `coverage_summary` LEFT-JOINs from the catalog, so the Overview
  headline «مشاهدات لایه طلایی» reports **8,195** (the 50 catalog-joined base
  series) while `gold.gold_analytical` holds **20,074** rows; the 11,879 derived
  rows are excluded from that metric and surfaced separately as «سری‌های
  مشتق‌شده» (32). The number is internally consistent with the coverage table but
  can be read as a total-Gold count. Flagged as a follow-up candidate, not an
  acceptance blocker.
- **Overview "series without a catalog row" metric is 32, not genuine orphans.**
  The metric `metric.orphan_series` («سری‌های بدون ردیف فهرست») counts series
  whose own id has no catalog row — the 32 derived series, all of which inherit a
  resolvable parent. **Genuine orphans are 0.** The label is accurate; the plan's
  "orphan" wording is broader than the displayed metric.
- **One chain-linking data nuance.** 12 of the 240 `SCI.CPI.URBAN.YOY` rows are
  flagged `is_chain_linked` with a null `original_value`. The dashboard displays
  this as stored (no value is invented); the nulls are an ETL-side property.
- **Derived-series count is 32, not the plan's ≈38.** Recorded above; the plan
  figure was indicative.

## Explicit Note On Forecasts

Because forecast labeling is deferred (an ETL change under `src/` would be
required), **IMF WEO forecast rows are displayed exactly like actual
observations** in this release. The Overview carries an explicit Persian
disclaimer to that effect; no forecast-specific styling, filtering or labeling
exists.

## Validation Conclusion

The Phase 7.1 implementation is **static-clean, type-checked and validated**
(1,157 unit tests, 89.22% coverage; 340 dashboard tests; 131 integration tests,
0 failed), keeps the `src/` boundary, launches headless, and — as recorded in
Level 5 — **renders every page against a populated database with zero
exceptions** while exposing derived series, chain-linking provenance, Jalali
display, localized exports, catalog search, correlation guardrails and freshness
verdicts.

Two acceptance criteria remain deliberately unmet and are recorded, not hidden:
the **cache TTL / refresh control** (a pipeline run needs an app restart) and
the **human `make dashboard` browser click-through** (its equivalent was
performed programmatically). The Overview observations metric being
catalog-scoped, and the derived count being 32 rather than the plan's indicative
≈38, are documented observations rather than blockers.

**Recommendation: ACCEPT Phase 7.1**, with the cache-TTL/refresh item carried
forward as the single open acceptance criterion.
