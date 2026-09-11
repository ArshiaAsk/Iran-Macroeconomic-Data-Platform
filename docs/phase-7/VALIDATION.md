# Phase 7 Validation Report

**Status:** ✅ DASHBOARD VALIDATED — September 11, 2026

This report records the commands and outcomes used to validate the Phase 7
dashboard implementation. The dashboard-specific, static, integration, and launch
validations pass. The project-wide unit command also exposed a pre-existing,
unrelated Gold ETL test issue, recorded below.

## Validated Environment

| Component | Version |
|-----------|---------|
| Poetry | 2.4.1 |
| Python | 3.12.3 |
| Streamlit | 1.61.1 |
| Plotly | 6.9.0 |
| Kaleido | 1.4.0 |
| openpyxl | 3.1.5 |
| pandas | 2.3.3 |
| SQLAlchemy | 2.0.52 |
| pytest | 7.4.4 |

## Level 1: Dependency Validation

```bash
poetry install
poetry run python -c "import openpyxl, kaleido"
```

✅ **Result:** dependencies resolved and imported successfully.

The lockfile was regenerated locally. `poetry.lock` is intentionally ignored by
this repository's current `.gitignore`.

## Level 2: Formatting And Static Analysis

```bash
make format
make lint
make typecheck
```

✅ **Result:**

- `ruff format` completed successfully.
- `ruff check` reported no errors.
- `mypy src/` reported `Success: no issues found`.

An additional explicit check was run:

```bash
poetry run mypy src dashboard
```

✅ **Result:** `Success: no issues found in 41 source files`.

## Level 3: Dashboard Unit And AppTest Validation

```bash
poetry run pytest tests/unit/dashboard -v --no-cov
```

✅ **Result:** **24 passed**.

Coverage includes:

- Repository shaping
- Cached connection
- Filters
- Chart construction
- Exports
- Quality calculations
- Offline `AppTest` smoke tests for all seven pages

## Level 4: Static Chart Export Validation

A real Plotly figure was rendered to both static formats using the implemented
Kaleido path and a local Chromium executable.

✅ **Result:**

- PNG returned non-empty image bytes.
- SVG began with `<svg class="main-svg`.

The test suite mocks the Chromium renderer to keep unit tests fast and
environment-independent. Real rendering was separately verified with Chromium.

## Level 5: Database And Migration Validation

```bash
make db-up
poetry run alembic upgrade head
```

✅ **Result:**

- PostgreSQL/TimescaleDB container was healthy.
- Alembic applied migrations without error.
- No Phase 7 migration was required.

## Level 6: Dashboard Integration Validation

```bash
poetry run pytest tests/integration/test_dashboard_repository.py \
  -m integration -v --cov-fail-under=0
```

✅ **Result:** **2 passed**.

The integration tests seed real catalog, Bronze, Silver, Gold, and
collection-log rows in PostgreSQL, execute the dashboard repository queries, and
roll back the transaction.

## Level 7: Full Integration Regression

```bash
poetry run pytest tests/integration/ -m integration -v --cov-fail-under=0
```

✅ **Result:** **46 passed, 2 skipped**.

The two skipped tests are live external-source tests gated behind
`RUN_LIVE_API_TESTS=1`; they are intentionally not run in the normal validation
path.

This suite includes the existing database, TGJU pipeline, World Bank pipeline,
and new dashboard repository integration tests.

## Level 8: Project-Wide Unit Validation

```bash
make test
```

⚠️ **Result:** **348 passed, 10 failed**; coverage was 84.50%.

All 10 failures are in `tests/unit/etl/test_gold.py` daily derived-metric tests:

```text
test_silver_to_gold_daily_strategy_derives_ret1d
test_silver_to_gold_daily_strategy_derives_ma30
test_daily_ret1d_values_are_correct
test_daily_ma30_values_are_correct
test_daily_strategy_skips_first_return
test_daily_strategy_skips_first_29_ma
test_daily_derived_series_have_correct_indicator_ids
test_yoy_strategy_does_not_publish_daily_metrics
test_daily_strategy_with_custom_prefix
test_daily_metrics_metadata_in_gold
```

The failures occur because the test helper stages catalog rows in `FakeSession`
without flushing them, so `_resolve_catalog_entry()` cannot find the catalog and
logs `no domain found for indicator`. The same behavior is visible before any
dashboard query is involved.

Phase 7 does not modify `src/etl/gold.py`, `tests/unit/etl/test_gold.py`, or
`tests/conftest.py`. The issue is pre-existing and should be fixed separately.

## Level 9: Dashboard Launch Validation

```bash
make dashboard
```

✅ **Result:** Streamlit started in the foreground and reported:

```text
Uvicorn server started on :::8501
Local URL: http://localhost:8501
Network URL: http://172.20.10.4:8501
```

The launch was stopped with the timeout used for non-interactive validation.

## Data Validation Checks

✅ **Verified:**

- Dashboard observations come only from `gold.gold_analytical`.
- Multi-indicator queries preserve indicator selection order.
- Timestamps remain timezone-aware.
- Date-range filters are applied in SQL.
- Coverage and freshness use `IndicatorCatalog` and `DataCollectionLog`.
- Export row counts match selected database rows.
- Units and indicator metadata remain attached to exports.
- Original values, chain-linking flags, and confidence are exported.
- No interpolation, forward-fill, or resampling is introduced.
- Exact-timestamp correlation reports actual join counts.
- Sparse TGJU history is explicitly warned about.
- Catalog `NULL` availability is represented as unknown.

## Manual Validation Status

### Completed

- Documentation review for `docs/phase-7/README.md`.
- Real static PNG/SVG rendering.
- Real PostgreSQL repository integration.
- Offline page smoke tests with Streamlit `AppTest`.
- Headless dashboard launch against the configured database.

### Not Automated In This Run

Interactive browser click-through of every filter, chart, and download button
against a populated local Gold database was not performed. The underlying logic
is covered by unit, AppTest, export, and repository integration tests, but a
final analyst-facing browser review is still recommended:

```bash
make dashboard
```

## Validation Conclusion

The Phase 7 dashboard implementation is validated and ready for analyst use.
The only failing project-wide validation is the unrelated pre-existing Gold ETL
unit-test issue documented above; it does not affect the dashboard query,
rendering, export, or integration behavior added in this phase.
