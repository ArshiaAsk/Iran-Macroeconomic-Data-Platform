# Phase 7.1 Validation Report

**Status:** ✅ Implemented (Tasks 1–25) — documentation recorded 2026-09-19.
**Plan:** [phase-7.1-dashboard-refresh.md](../plans/phase-7.1-dashboard-refresh.md)
**Runbook:** [README.md](README.md) · **Implementation:** [IMPLEMENTATION.md](IMPLEMENTATION.md)

This report records the commands and outcomes actually observed for the
implementation that shipped. It distinguishes **verified in this run** from
**not automated in this run**. Tasks 27 (extended test suite) and 28 (analyst
acceptance pass) are **not yet executed**; their absence is recorded as a gap,
not as a pass.

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
  but bypasses the router, so the per-page harness stayed on direct page files
  and nav/ownership assertions are made against the registry.

---

## Level 1: Static / Style

```bash
poetry run ruff check dashboard src tests
poetry run ruff format --check dashboard src tests
poetry run mypy src dashboard
```

✅ **Result (observed 2026-09-19):**

- `ruff check` — no errors.
- `ruff format --check` — `140 files already formatted`.
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

✅ **Result:** **324 passed** across 13 test files, including repository
shaping, derived/orphan discovery, derived-series labels, navigation/domain
ownership, Persian string catalog and label coverage, formatting (digits,
Jalali, Tehran round-trip), filters (Jalali presets), RTL direction, chart
scaling, tables, exports, quality, and offline `AppTest` smoke tests for every
page.

## Level 2b: Project-Wide Unit Tests

```bash
poetry run pytest tests/unit -q
```

✅ **Result:** **1,141 passed, 3 skipped**, coverage **89.22%** (gate 80%).

The three skips are live-source tests gated behind `RUN_LIVE_API_TESTS=1`.
`tests/unit/etl/test_gold.py` — the 10 failures recorded in the Phase 7 report —
now passes (62 passed).

---

## Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
```

⚠️ **Result:** **128 passed, 4 skipped, 1 failed** (517 s).

The four skips are live external-source tests gated behind
`RUN_LIVE_API_TESTS=1`.

**The one failure is a stale assertion, not a product defect:**

```text
FAILED tests/integration/test_dashboard_repository.py::test_selected_export_contains_exact_database_rows
AssertionError: assert 'chain_linking_confidence' in '<CSV …>'
```

The test asserts the raw English column name `chain_linking_confidence` appears
in the CSV. Phase 7.1 localized export headers to Persian
(`اطمینان زنجیرهسازی` is present in the produced CSV; the chain-linking columns
are exported as required), so the English header no longer appears. The export
behavior is correct; the integration assertion was not updated when exports were
localized (Task 21). Fixing it is part of Task 27, which is deferred — see
[Remaining Gaps](#remaining-gaps).

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

## Remaining Gaps

- **Task 27 (extended test suite) is not executed.** In particular, the **AST
  literal guard** against untranslated Streamlit literals is **not present**, and
  the integration suite does not yet seed a future-dated (IMF) row for the
  forecast-indistinguishability assertion. (Domain-ownership, Jalali round-trip,
  and derived/orphan tests did land with their feature tasks.)
- **One stale integration test fails** (`test_selected_export_contains_exact_database_rows`,
  above); it needs the Persian-header expectation in Task 27.
- **Task 28 (analyst acceptance pass) is not executed.** Interactive browser
  click-through of every page, filter, chart and download against a populated
  database was not performed. The underlying logic is covered by unit,
  AppTest, export and repository tests, but a final analyst-facing browser review
  is still required:

  ```bash
  make dashboard
  ```

- **Cache TTL / refresh control** (accepted deviation 1) remains an open
  acceptance criterion.
- **Counts are not re-derived from a real populated run.** The catalog shape
  (≈50 active indicators across 9 domains, 4 inactive SCI base-year segments,
  ≈38 derived Gold series) comes from the connector registries and the plan; it
  is **indicative** until Task 28 re-derives it from a real run, as the plan
  requires.

## Explicit Note On Forecasts

Because forecast labeling is deferred (an ETL change under `src/` would be
required), **IMF WEO forecast rows are displayed exactly like actual
observations** in this release. The Overview carries an explicit Persian
disclaimer to that effect; no forecast-specific styling, filtering or labeling
exists.

## Validation Conclusion

The Phase 7.1 implementation is **static-clean, type-checked and unit-validated**
(1,141 unit tests, 89.22% coverage; 324 dashboard tests), keeps the `src/`
boundary, and launches. It is **not fully validated** end to end: one stale
integration assertion fails, the AST literal guard and the analyst acceptance
pass (Tasks 27–28) are outstanding, and the cache TTL/refresh acceptance
criterion is unmet. These are recorded above rather than treated as passes.
