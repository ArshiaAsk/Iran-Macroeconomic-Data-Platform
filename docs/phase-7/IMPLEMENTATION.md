# Phase 7 Implementation Report

**Status:** ✅ IMPLEMENTED — September 11, 2026

> **Superseded by [Phase 7.1](../phase-7.1/IMPLEMENTATION.md)** for navigation,
> page structure, localization and several behaviors. Corrections to this Phase 7
> record are marked **Correction** below; the Phase 7 data contract still holds.

Phase 7 adds the first user-facing analytics surface for the platform. The
dashboard reads the validated Gold analytical layer and indicator metadata,
provides domain-specific exploration, preserves data-quality context, and exports
selected observations and charts without requiring SQL access.

## What Was Built

### Application Structure

- Streamlit entry point at `dashboard/app.py`.
- Multipage navigation under `dashboard/pages/` (Phase 7 list):
  - Overview
  - Inflation
  - GDP & Economy
  - Trade, Welfare & Energy
  - FX & Gold
  - Comparison & Correlation
  - Data Catalog
- Shared page composition in `dashboard/page_view.py`.

> **Correction (Phase 7.1).** The shipped dashboard has ten pages: the
> "Trade, Welfare & Energy" page became **Trade & Energy**, and **Welfare &
> Survey**, **Market** and **Labor** pages were added. Navigation is now an
> `st.navigation` router driven by a declarative page registry
> (`dashboard/navigation.py`) instead of implicit `pages/` discovery. See
> [Phase 7.1 IMPLEMENTATION.md](../phase-7.1/IMPLEMENTATION.md).
- Local foreground launch target:

  ```bash
  make dashboard
  ```

### Query And Connection Layer

- `dashboard/repository.py` provides an injected-session, read-only repository
  over:
  - `gold.gold_analytical`
  - `metadata.indicator_catalog`
  - `metadata.data_collection_log`
- Repository methods cover:
  - Catalog search and filtering
  - Multi-indicator Gold loading
  - Coverage summaries
  - Source freshness
  - Available domains
- `dashboard/connection.py` creates one `st.cache_resource`-cached
  `DatabaseConnection` pool instead of mutating the global ETL singleton.
- `dashboard/queries.py` adds `st.cache_data` wrappers for query DataFrames.
  Cache keys include catalog filters, indicator IDs, and date bounds.
- The repository does not commit, mutate data, call Streamlit, or initialize a
  global database connection.

### Shared Components

- **Filters** (`dashboard/components/filters.py`)
  - Indicator, domain, frequency, source, and date controls
  - Default bounds derived from observed catalog coverage
  - Invalid date-range error handling
- **Charts** (`dashboard/components/charts.py`)
  - Multi-indicator time-series panels
  - Original-versus-chain-linked comparison (built here; surfaced on a page only
    in Phase 7.1 — see the correction under "Page Behavior")
  - Exact-timestamp correlation heatmap
  - Coverage summary chart

> **Correction (Phase 7.1).** The `build_coverage_chart` helper was **deleted**
> in Phase 7.1 (the Overview uses metrics and tables instead). The
> original-vs-chain-linked chart and derived growth series were **not reachable
> in the Phase 7 UI**: the chart was called only from a unit test, and derived
> Gold series were unreachable because `load_series` inner-joined the catalog
> while the catalog is seeded only from `discover()` (which never emits derived
> ids). Phase 7.1 exposed both.
- **Exports** (`dashboard/components/exports.py`)
  - UTF-8 CSV
  - Excel `.xlsx`
  - Standalone interactive HTML
  - PNG and SVG static images
  - ISO-8601 timezone-aware timestamps and serialized metadata
- **Quality** (`dashboard/components/quality.py`)
  - Rows returned versus expected observations
  - Missing-period counts
  - Chain-linked row counts and confidence
  - Sparse-history and TGJU snapshot warnings

### Page Behavior

- **Overview** shows active indicator counts, Gold observation totals, domain
  counts, source counts, observed coverage, and latest collection results.
- **Inflation** treats `FP.CPI.TOTL.ZG` as an annual inflation rate, not a CPI
  index.
- **GDP & Economy** supports levels and derived annual growth series when they
  exist in Gold. **Correction (Phase 7.1):** derived series were *not* reachable
  in the Phase 7 UI — the "include derived" toggle validated hardcoded
  candidates against the catalog and was inert in production. Phase 7.1 exposes
  them through metadata-driven discovery.
- **Trade, Welfare & Energy** keeps mixed-unit indicators in separate chart
  panels and does not normalize values silently. **Correction (Phase 7.1):**
  this page is now **Trade & Energy**; the `welfare` domain moved to the
  **Welfare & Survey** page.
- **FX & Gold** explicitly identifies TGJU as a snapshot source and warns when
  history is sparse.
- **Comparison & Correlation** uses exact timestamp matches and displays a
  join-count matrix. It does not forward-fill or interpolate mixed frequencies.
- **Data Catalog** exposes IDs, names, descriptions, units, domains, sources,
  source URLs, availability, base-year flags, and active status. `NULL`
  availability is displayed as unknown.

## Dependencies

Added:

- `openpyxl` for Excel export.
- `kaleido` for Plotly static image export.

Updated:

- `plotly` from `^5.18.0` to `^6.1.1`.

The Plotly upgrade is required because Kaleido 1.x is the supported static
export path and reports incompatibility with Plotly 5.24. The resolved versions
used during validation were Plotly 6.9.0 and Kaleido 1.4.0.

PNG/SVG rendering requires a Chromium executable. The dashboard discovers a
standard Google Chrome installation, Playwright Chromium, or Plotly's managed
Chrome. `DASHBOARD_CHROME_PATH` can override discovery.

## Data Safety

- The dashboard reads Gold for observations; it does not read Silver or Bronze
  for analytical values.
- No interpolation, forward-fill, resampling, or artificial frequency conversion
  is introduced.
- Original and chain-linked values remain separate.
- Missing observations remain missing and are surfaced as quality diagnostics.
- No database schema migration was required or added.
- No new external data source, forecasting model, or real-time channel was added.

## Tests Added

### Unit And AppTest

`tests/unit/dashboard/` covers:

- Repository DataFrame shaping and stable empty-series columns
- Cached connection behavior
- Filter option generation and default date bounds
- Time-series, chain-linking, and correlation chart construction
- CSV, Excel, HTML, PNG, and SVG export behavior
- Quality and gap calculations
- Offline `AppTest` smoke tests for every dashboard page

### Integration

`tests/integration/test_dashboard_repository.py` seeds catalog, Bronze, Silver,
Gold, and collection-log rows in a rolled-back PostgreSQL transaction and
validates:

- Catalog search and filters
- Date filtering
- Timezone-aware timestamps
- Coverage summaries
- Source freshness
- Export row counts and quality columns

## Deferred Items

- Monetary-domain page: no monetary indicators are loaded yet (CBI TSD is
  gated).
- ~~CPI decile analysis: decile-level CPI data is not loaded yet.~~
  **Correction (Phase 7.1):** the ten SCI expenditure-decile CPI series have
  existed in the catalog since Phase 5 and are surfaced on the Phase 7.1
  Inflation page. This deferral was based on a false premise.
- Authentication, multi-user authorization, cloud deployment, and mobile-specific
  design remain out of scope.

See the [Phase 7.1 deferred scope](../phase-7.1/README.md#deferred-scope-phase-72-candidates)
for the current deferral list.

## Key Files

| Area | File |
|------|------|
| Entry point | `dashboard/app.py` |
| Repository | `dashboard/repository.py` |
| Cached connection | `dashboard/connection.py` |
| Cached queries | `dashboard/queries.py` |
| Page composition | `dashboard/page_view.py` |
| Page modules | `dashboard/pages/` |
| Filters | `dashboard/components/filters.py` |
| Charts | `dashboard/components/charts.py` |
| Exports | `dashboard/components/exports.py` |
| Quality | `dashboard/components/quality.py` |
| Unit tests | `tests/unit/dashboard/` |
| Integration tests | `tests/integration/test_dashboard_repository.py` |
| Runbook | `docs/phase-7/README.md` |
