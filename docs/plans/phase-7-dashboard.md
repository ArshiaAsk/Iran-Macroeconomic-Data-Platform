# Task: Phase 7 Dashboard

## Task Description

Implement the interactive Streamlit dashboard described in `PRD.md` Task 16–18.
The dashboard will make the validated Gold analytical layer usable by economists
without writing SQL: it will provide a multi-page layout, shared filtering,
interactive Plotly time-series charts, a data catalog, data-quality context, and
CSV/Excel/chart exports.

This phase consumes the data already produced by the World Bank and TGJU
pipelines. It does not add data sources or transform data. It is the first
user-facing analytics surface for the platform.

```text
As an economic analyst
I want to search, explore, compare, and export Iran macroeconomic time series
So that I can perform research and produce publication-ready outputs without
direct database access
```

## Scope

### In Scope

- [ ] Create the Streamlit entry point and multipage application structure.
- [ ] Add a dashboard query/repository layer over `GoldAnalytical`,
      `IndicatorCatalog`, and `DataCollectionLog`.
- [ ] Add shared components for indicator selection, date-range filtering,
      source/domain/frequency filtering, and downloads.
- [ ] Build an overview page with coverage and freshness summaries.
- [ ] Build domain-specific pages for available data:
      inflation, GDP/economy, trade/welfare/energy, and FX/gold.
- [ ] Build a searchable data catalog page with metadata and source links.
- [ ] Build interactive Plotly charts for:
      single-indicator analysis, multi-indicator comparison, and correlation
      heat maps.
- [ ] Add chart exports as PNG, SVG, and standalone interactive HTML.
- [ ] Add selected-data exports as CSV and Excel.
- [ ] Show data-quality context:
      chain-linked versus original values, confidence, coverage, gaps, and
      source freshness.
- [ ] Add Streamlit caching and efficient database connection pooling.
- [ ] Add unit and integration tests for query logic, chart construction,
      exports, and page loading.
- [ ] Update README and add a dashboard runbook.

### Out of Scope

- [ ] IMF, EIA, OPEC, CBI, SCI, TSETMC, or HBSIR connectors.
- [ ] Forecasting or other ML models.
- [ ] Real-time or WebSocket updates.
- [ ] Authentication, multi-user authorization, or cloud deployment.
- [ ] Mobile-specific design.
- [ ] Read replicas or advanced TimescaleDB performance tuning.
- [ ] New database schemas or migrations.
- [ ] Full CPI decile analysis because decile-level CPI data is not yet loaded.
- [ ] Monetary-domain page because no monetary indicators are loaded yet.

## Context

**Current state:** Phases 1–3 are complete. The platform already has:

- A PostgreSQL/TimescaleDB medallion schema.
- A validated World Bank pipeline with 12 annual indicators.
- A validated TGJU scraper with three daily FX/gold indicators.
- `GoldAnalytical` as the intended analysis-ready source.
- `IndicatorCatalog` as the source of searchable metadata.
- `DataCollectionLog` as the source of freshness information.
- Streamlit and Plotly dependencies, but no dashboard implementation.

The `dashboard/` directory currently contains only `__init__.py`. The documented
entry point `streamlit run dashboard/app.py` does not exist yet.

**Available data domains:**

- World Bank: `gdp`, `inflation`, `trade`, `welfare`, and `energy`.
- TGJU: `fx` and `gold`.
- Monetary and CPI decile data are not yet available, so those requested pages
  must not be created as empty placeholders.

**Important implementation constraints:**

- The dashboard must read from Gold, not Silver or Bronze.
- No values should be interpolated to fill gaps.
- Daily TGJU history is accumulated through repeated runs and may initially be
  sparse; the UI must display actual coverage rather than implying a complete
  historical series.
- Derived TGJU moving averages and returns must not be shown until sufficient
  history exists; if already present in Gold, they can be displayed as ordinary
  selectable indicators.
- Database timestamps are timezone-aware and must remain timezone-aware in
  queries and exported files.
- The Python attribute for JSONB metadata is `record_metadata`, while the
  physical database column is `metadata`.
- All public functions need complete type hints.
- Unit tests must not require a database, browser, network, or Streamlit server.

## Proposed Approach

Build a thin presentation layer over a testable repository/service layer:

1. **Query layer first** — add a dashboard repository that accepts an injected
   SQLAlchemy `Session` and exposes catalog, series, coverage, and freshness
   queries. Keep SQL and DataFrame shaping out of page code.
2. **Shared UI components second** — implement reusable filter, chart, quality,
   and export components. Pages compose these components instead of duplicating
   logic.
3. **Pages third** — implement the entry point and pages using the repository
   and shared components. Render only domains that currently have data.
4. **Exports fourth** — use pandas for CSV/Excel and Plotly for HTML/PNG/SVG.
   Add the missing `openpyxl` and `kaleido` dependencies.
5. **Validation last** — unit-test pure query/chart/export logic with fake or
   fixture sessions, integration-test repository behavior against PostgreSQL,
   and use Streamlit's `AppTest` framework for page smoke tests.

This keeps Streamlit code simple, makes business logic testable without a
running server, and avoids duplicating query/filter behavior across pages.

## Task Metadata

**Type:** New Capability
**Complexity:** High
**Affected Areas:** Dashboard, database query layer, dependencies, tests, documentation
**Dependencies:** Phase 1 database schema; Phase 2 World Bank Gold data; Phase 3 TGJU Gold data; existing Streamlit, Plotly, SQLAlchemy, and pandas dependencies

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `PRD.md` - Phase 7 requirements in Tasks 16–18 and final acceptance criteria.
- `README.md` - Current dashboard command, project status, roadmap, and testing commands.
- `AGENTS.md` - Project conventions, data rules, naming rules, and testing rules.
- `src/database/schema.py` - `GoldAnalytical`, `IndicatorCatalog`, and `DataCollectionLog` models.
- `src/database/connection.py` - Existing `DatabaseConnection`, session management, and connection pooling pattern.
- `src/etl/gold.py` - Existing `load_gold_series()` behavior and Gold output columns.
- `src/utils/config.py` - Existing typed configuration and database URL construction.
- `src/utils/logging.py` - Structured logging and context logging conventions.
- `src/utils/validation.py` - Existing date, null, and quality-validation semantics.
- `tests/unit/etl/test_gold.py` - DataFrame and ORM query test patterns.
- `tests/integration/test_database.py` - PostgreSQL/TimescaleDB integration test pattern.

### Data / ML References

- `src/etl/pipeline.py` - World Bank publication flow and catalog availability updates.
- `src/connectors/tgju_scraper.py` - TGJU domain registry and single-observation history limitations.
- `docs/phase-2/data_dictionary.md` - Observed World Bank and TGJU indicator coverage, units, and known gaps.
- `src/etl/gold.py` - Derived annual YoY and daily return/moving-average identifier conventions.

### External Documentation

- Streamlit multipage apps: https://docs.streamlit.io/develop/concepts/multipage-apps -
  confirms the `pages/` directory layout and navigation behavior.
- Streamlit app testing: https://docs.streamlit.io/develop/api-reference/app-testing -
  confirms `streamlit.testing.v1.AppTest` for server-free page smoke tests.
- Plotly static image export: https://plotly.com/python/static-image-export/ -
  confirms that PNG/SVG export requires the `kaleido` package.

### Patterns to Follow

**Naming:** snake-case modules and functions; PascalCase classes; no hardcoded
URLs, timeouts, or export limits in page logic.

**Structure:** one dashboard responsibility per module; repository, components,
and pages remain separate.

**Testing:** pure unit tests with injected sessions and DataFrames;
integration tests marked `pytest.mark.integration`; no network or live database
in unit tests.

**Data:** Gold is the only analytical input; preserve timestamps, units, source
metadata, original values, and chain-linking flags; never interpolate by default.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

Prepare dependencies, query interfaces, and application scaffolding before
building pages.

### Phase 2: Core Change

Implement the repository, shared components, and chart/export functions.

### Phase 3: Integration

Compose the entry point and all pages, connect them to Gold and metadata, and
update documentation.

### Phase 4: Validation

Run static checks, unit tests, integration tests, app smoke tests, and manual
validation against a populated local database.

---

## STEP-BY-STEP TASKS

Execute tasks in dependency order.

### UPDATE dependencies

- **IMPLEMENT:** Add `openpyxl` for Excel export and `kaleido` for Plotly PNG/SVG
  export to `pyproject.toml` and regenerate `poetry.lock`.
- **PATTERN:** Existing dependency declarations in `pyproject.toml`.
- **DEPENDENCIES:** None.
- **GOTCHA:** Do not add a separate frontend stack or dashboard framework.
- **VALIDATE:** `poetry install && poetry run python -c "import openpyxl, kaleido"`

### CREATE dashboard repository

- **IMPLEMENT:** Create `dashboard/repository.py` with an injected-session
  repository exposing:
  - `list_indicators(search, domains, frequencies, sources, active_only)`
  - `load_series(indicator_ids, start_date, end_date)`
  - `coverage_summary(indicator_ids)`
  - `source_freshness()`
  - `available_domains()`
- **PATTERN:** `src/etl/gold.py:655` for Gold querying and
  `src/database/connection.py:63` for session ownership.
- **DEPENDENCIES:** SQLAlchemy models in `src/database/schema.py`.
- **GOTCHA:** The repository must not call `st.*`, initialize a global database,
  commit, or mutate data.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_repository.py`

### CREATE dashboard connection helper

- **IMPLEMENT:** Add a small Streamlit connection module that constructs a
  `DatabaseConnection` from `get_config().database.url` and caches it with
  `st.cache_resource`.
- **PATTERN:** `src/database/connection.py:154` for initialization.
- **DEPENDENCIES:** Dashboard repository; `AppConfig`.
- **GOTCHA:** Prefer a local cached `DatabaseConnection` over mutating the
  global ETL singleton. Closing is unnecessary for the long-lived cached pool.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_connection.py`

### CREATE shared filters

- **IMPLEMENT:** Create `dashboard/components/filters.py` with reusable
  indicator, domain, frequency, source, and date-range controls. Derive default
  date bounds from actual catalog coverage, not hardcoded years.
- **PATTERN:** Typed public functions with explicit `None` returns.
- **DEPENDENCIES:** Repository catalog query.
- **GOTCHA:** Store selections in `st.session_state` only where needed; avoid
  global mutable state.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_filters.py`

### CREATE chart builders

- **IMPLEMENT:** Create `dashboard/components/charts.py` with pure functions
  returning Plotly figures:
  - time-series chart for one or more indicators
  - original-versus-chain-linked comparison
  - correlation heatmap for selected indicators
  - coverage/freshness summary chart
- **PATTERN:** Pure DataFrame-in, figure-out functions, similar to the parser's
  separation from scraper transport.
- **DEPENDENCIES:** pandas and Plotly only.
- **GOTCHA:** Do not aggregate or resample inside chart builders. A chart
  displays exactly the rows supplied by the repository.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_charts.py`

### CREATE export functions

- **IMPLEMENT:** Create `dashboard/components/exports.py` for:
  - CSV serialization
  - Excel serialization
  - Plotly standalone HTML
  - Plotly PNG and SVG images
  - Streamlit download buttons
- **PATTERN:** Existing dependency-injection and validation style.
- **DEPENDENCIES:** `openpyxl`, `kaleido`, Plotly, pandas.
- **GOTCHA:** Include indicator metadata, units, timestamps, and quality flags
  in exported data. Preserve timezone-aware timestamps as ISO-8601 strings.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_exports.py`

### CREATE quality components

- **IMPLEMENT:** Add reusable components that summarize:
  - rows returned versus expected coverage
  - missing periods/gaps
  - chain-linked row count and confidence
  - original versus linked values
  - source last-collection timestamp
- **PATTERN:** Use `src/utils/validation.py` semantics; do not invent a second
  quality model.
- **DEPENDENCIES:** Repository output and catalog metadata.
- **GOTCHA:** Missing data must be visible, not silently filled.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_quality.py`

### CREATE application entry point

- **IMPLEMENT:** Create `dashboard/app.py` with app configuration, shared page
  header, database status, navigation, and a concise overview.
- **PATTERN:** Streamlit multipage convention using `dashboard/pages/`.
- **DEPENDENCIES:** Connection helper and repository.
- **GOTCHA:** Do not place page modules under `src/`; the existing package
  layout already supports `dashboard/`.
- **VALIDATE:** `poetry run streamlit run dashboard/app.py --server.headless true`

### CREATE overview page

- **IMPLEMENT:** Add `dashboard/pages/1_Overview.py` showing indicator counts by
  domain/source/frequency, total Gold observations, available coverage, source
  freshness, and quick links to key indicators.
- **PATTERN:** Shared components only; no page-local SQL.
- **DEPENDENCIES:** Repository and chart builders.
- **GOTCHA:** Freshness should reflect `DataCollectionLog`, not the current wall
  clock alone.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_overview.py`

### CREATE economy pages

- **IMPLEMENT:** Add pages for inflation and GDP/economy. Each page should
  support indicator filtering, date ranges, single/multi-series charts, growth
  toggles where derived series exist, quality summaries, and exports.
- **PATTERN:** Reuse the same shared filter/chart/export components.
- **DEPENDENCIES:** World Bank Gold rows.
- **GOTCHA:** `FP.CPI.TOTL.ZG` is an annual inflation rate, not a CPI index;
  do not label or difference it as an index.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_economy.py`

### CREATE trade and welfare page

- **IMPLEMENT:** Add a page for `trade`, `welfare`, and `energy` indicators.
- **PATTERN:** Domain page composition from shared components.
- **DEPENDENCIES:** World Bank Gold rows.
- **GOTCHA:** Units differ across indicators; do not force a shared y-axis
  without separate axes or explicit normalization.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_trade_welfare.py`

### CREATE FX and gold page

- **IMPLEMENT:** Add a page for `fx` and `gold` TGJU indicators, including
  latest values, observed daily coverage, and explicit warnings when history is
  sparse.
- **PATTERN:** TGJU data dictionary coverage guidance.
- **DEPENDENCIES:** TGJU Gold rows.
- **GOTCHA:** TGJU is a snapshot source. The page must not imply that a full
  historical backfill exists.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_fx_gold.py`

### CREATE data catalog page

- **IMPLEMENT:** Add `dashboard/pages/5_Data_Catalog.py` with search, domain,
  frequency, and source filters; indicator names, IDs, units, domains, sources,
  source links, availability, base-year flags, and active status.
- **PATTERN:** `IndicatorCatalog` fields in `src/database/schema.py:167`.
- **DEPENDENCIES:** Repository catalog query.
- **GOTCHA:** Availability is observed coverage and may be `NULL`; display it as
  unknown rather than as 1960–present.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_catalog.py`

### CREATE correlation page

- **IMPLEMENT:** Add a comparison/correlation page that selects multiple
  indicators, aligns observations only where timestamps actually match, and
  renders a correlation heatmap with an explicit join-count matrix.
- **PATTERN:** pandas correlation over the repository's returned rows.
- **DEPENDENCIES:** Chart builders and shared filters.
- **GOTCHA:** Annual and daily indicators cannot be meaningfully correlated on
  exact timestamps. Restrict or clearly label join behavior rather than
  forward-filling by default.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_correlation.py`

### UPDATE dashboard documentation

- **IMPLEMENT:** Update README quick start and add
  `docs/phase-7/README.md` with prerequisites, launch steps, page guide, export
  instructions, troubleshooting, and known data limitations.
- **PATTERN:** `airflow/README.md` and existing phase documentation style.
- **DEPENDENCIES:** Completed dashboard behavior.
- **GOTCHA:** Do not claim CPI deciles, monetary analytics, real-time data, or
  mobile support.
- **VALIDATE:** Manual documentation review.

### ADD dashboard Makefile target

- **IMPLEMENT:** Add a `dashboard` target that runs Streamlit with the expected
  local entry point.
- **PATTERN:** Existing Makefile command style.
- **DEPENDENCIES:** `dashboard/app.py`.
- **GOTCHA:** Keep the target local and foreground; do not start Docker or
  Airflow automatically.
- **VALIDATE:** `make dashboard`

---

## TESTING & VALIDATION

### Unit Tests

- Repository query construction and DataFrame shaping with fake sessions.
- Empty catalog, no matching indicators, and invalid/empty date ranges.
- Filter option generation and default date bounds.
- Time-series and correlation chart construction from fixture DataFrames.
- CSV/Excel/HTML/PNG/SVG export behavior.
- Quality and gap calculations.
- Streamlit `AppTest` smoke tests for each page.

### Integration Tests

- Seed catalog and Gold rows in the existing integration database.
- Validate indicator search/filter behavior.
- Validate date-range filtering and timezone-aware timestamps.
- Validate source freshness queries.
- Validate CSV/Excel export against seeded Gold rows.
- Keep all integration tests marked `pytest.mark.integration`.

### Data Validation

- Dashboard reads only `gold.gold_analytical` for observations.
- No interpolation, forward-fill, or resampling occurs by default.
- Exported row counts match selected database rows.
- Units and indicator metadata remain attached to exported observations.
- Chain-linked and original values are preserved when present.
- Sparse TGJU history is explicitly surfaced.
- Catalog `NULL` availability is displayed as unknown.

### ML Validation

Not applicable. Phase 7 contains no model training, forecasting, inference, or
evaluation. No leakage-sensitive temporal methodology is introduced.

### Edge Cases

- No database connection or empty database.
- No indicators match the search/filter criteria.
- Start date is after end date.
- Selected range contains no observations.
- Indicator has `NULL` unit or availability.
- Annual and daily indicators are selected together.
- Indicators use incompatible units.
- Gold contains only a single TGJU observation.
- Derived series have insufficient history.
- Chain-linked and original values differ.
- Export selection contains Unicode indicator names and multiple frequencies.

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
make format
make lint
make typecheck
```

### Level 2: Unit Tests

```bash
make test
```

### Level 3: Integration / Pipeline Tests

```bash
make test-integration
```

### Level 4: Feature-Specific Validation

```bash
poetry run pytest tests/unit/dashboard -v
poetry run pytest tests/integration/test_dashboard_repository.py -v
```

### Level 5: Manual Validation

```bash
make db-up
poetry run alembic upgrade head
make dashboard
```

Manually verify:

- All pages render without exceptions.
- Overview counts match database queries.
- Catalog search returns expected World Bank and TGJU indicators.
- Date filters change both charts and exports.
- CSV, Excel, HTML, PNG, and SVG downloads contain the selected data/chart.
- Data-quality and sparse-history warnings appear when expected.
- Repeated navigation uses cached database resources without creating new pools.

---

## ACCEPTANCE CRITERIA

* [ ] Streamlit multipage dashboard launches with `make dashboard` and
      `streamlit run dashboard/app.py`.
* [ ] Overview, inflation, GDP/economy, trade/welfare/energy, FX/gold,
      correlation, and catalog pages load successfully.
* [ ] Indicator search and filtering work across source, domain, frequency,
      date range, and free-text fields.
* [ ] Charts render single and multiple selected indicators with correct units,
      axes, timestamps, and legends.
* [ ] Correlation behavior clearly handles annual/daily and sparse-data cases.
* [ ] CSV and Excel exports contain exactly the selected observations and
      metadata.
* [ ] Chart exports produce HTML, PNG, and SVG files.
* [ ] Data quality shows chain-linking, original values, confidence, coverage,
      gaps, and source freshness.
* [ ] TGJU snapshot and sparse-history limitations are visible in the UI.
* [ ] No interpolation or artificial frequency conversion is introduced.
* [ ] Unit, integration, lint, type-check, and test commands pass.
* [ ] README and Phase 7 runbook document setup, usage, and limitations.
* [ ] No regression occurs in existing ETL, connector, or database behavior.

---

## RISKS & TRADE-OFFS

* **Database dependency in UI tests:** Streamlit page tests can accidentally
  require PostgreSQL. Mitigate by injecting fake repositories/sessions or using
  `AppTest` with mocked connection helpers.
* **Query performance:** Unbounded multi-indicator Gold queries could become
  slow. Mitigate with indexed `(indicator_id, timestamp)` lookups, date bounds,
  reasonable selection limits, and `st.cache_data`.
* **Static chart export dependency:** `kaleido` adds a binary rendering
  dependency. It is required by Plotly for PNG/SVG and is the standard supported
  path.
* **Excel dependency:** `openpyxl` is required for `.xlsx`; adding it is simpler
  and more portable than implementing a custom writer.
* **Cross-frequency comparison:** Annual and daily series cannot be naively
  aligned. The UI must expose actual join counts rather than silently filling.
* **Sparse TGJU data:** A new deployment may have only one daily observation.
  The dashboard must explain this instead of displaying a misleading trend.
* **Domain mismatch with PRD:** Monetary and CPI-decile pages are requested but
  their source data is not implemented. They are deferred until Phase 4–6 data
  exists.
* **Documentation drift:** README currently references a nonexistent
  `dashboard/app.py`. The implementation must update documentation in the same
  change.

## NOTES

- Use `dashboard/repository.py` rather than adding a `src/dashboard/` package;
  this follows the existing top-level `dashboard/` package and keeps the
  presentation surface separate from ETL internals.
- Use `st.cache_resource` for the database connection/pool and `st.cache_data`
  for query result DataFrames. Cache keys must include all user selections.
- Keep page modules thin. Any logic worth testing belongs in the repository,
  filters, charts, exports, or quality modules.
- The existing `load_gold_series()` supports one indicator only. The dashboard
  repository should provide a multi-indicator query and must preserve ordering.
- Do not introduce a schema migration. All required fields already exist in
  `GoldAnalytical`, `IndicatorCatalog`, and `DataCollectionLog`.
- If current Gold data is unavailable during development, seed integration
  fixtures from the documented data dictionary; do not hit live external APIs in
  tests.
