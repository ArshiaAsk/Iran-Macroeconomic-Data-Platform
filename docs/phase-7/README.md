# Phase 7 Dashboard Runbook

> **Superseded for navigation, page structure, localization and quality behavior
> by [Phase 7.1](../phase-7.1/README.md)** (Persian/RTL UI, a `st.navigation`
> router, new Market/Labor/Welfare pages, Jalali dates, derived-series exposure,
> chain-linking transparency and catalog search). This document is kept as the
> Phase 7 record; the data contract it describes still holds.

The Streamlit dashboard publishes the validated Gold analytical layer without
requiring SQL access. It reads only from PostgreSQL; it does not call external
APIs, transform frequencies, or fill missing observations.

## Prerequisites

1. Install project dependencies:

   ```bash
   poetry install
   ```

2. Start PostgreSQL/TimescaleDB and apply migrations:

   ```bash
   make db-up
   poetry run alembic upgrade head
   ```

3. Populate Gold using one of the existing pipelines. For example:

   ```bash
   poetry run python -m src.connectors.world_bank
   ```

4. Confirm connectivity:

   ```bash
   make db-check
   ```

## Launch

```bash
make dashboard
```

Streamlit starts in the foreground at `http://localhost:8501`. Press `Ctrl+C`
to stop it. The equivalent direct command is:

```bash
poetry run streamlit run dashboard/app.py
```

## Page Guide

The Phase 7 page list below is **historical**. Phase 7.1 grew it to ten pages and
split the Welfare domain out; see
[Phase 7.1's Persian page guide](../phase-7.1/README.md#persian-page-guide) for
the current structure.

- **Overview** — active indicator counts, Gold observation totals, observed
  coverage, and the latest `DataCollectionLog` result per source.
- **Inflation** — annual inflation indicators. `FP.CPI.TOTL.ZG` is an annual
  rate, not a CPI index; it is never differenced as an index.
- **GDP & Economy** — GDP and economy indicators, including derived annual
  growth series when available.
- **Trade, Welfare & Energy** — mixed-unit World Bank indicators. Each series
  is charted in its own panel; values are not normalized automatically.
- **FX & Gold** — TGJU snapshot prices with an explicit sparse-history warning.
  Historical coverage accumulates through scheduled daily scrapes.
- **Comparison & Correlation** — exact-timestamp correlations. Mixed-frequency
  selections are not forward-filled; the join-count matrix shows the actual
  number of matched observations.
- **Data Catalog** — searchable indicator IDs, names, units, domains, sources,
  source links, availability, base-year flags, and active status.

> **Corrections for the Phase 7.1 refresh.** The Phase 7 pages above no longer
> match the shipped dashboard: the "Trade, Welfare & Energy" page became
> **Trade & Energy**, and **Welfare & Survey**, **Market** and **Labor** pages
> were added. Derived annual growth series were **not reachable in Phase 7**
> (the catalog is seeded only from `discover()`, which never emits derived ids,
> and `load_series` inner-joined the catalog); Phase 7.1 made them reachable
> through a metadata-driven discovery path. The chain-linking chart existed in
> Phase 7 but was called only from a unit test; Phase 7.1 surfaced it on the
> Inflation page. Catalog search across the Persian label layer and the
> inactive-base-year-segment toggle were also added in Phase 7.1.

## Filters And Exports

Domain pages support source, domain, frequency, indicator, and date filters.
Default date bounds come from observed catalog coverage, not hardcoded years.

> **Phase 7.1 additions.** Jalali year/month/day presets (with the applied
> Jalali label and UTC Gregorian bounds echoed back), an "include derived series"
> toggle, opt-in overlay and small-multiples chart modes, and catalog-page search
> were added in Phase 7.1. See
> [Phase 7.1's filters/search](../phase-7.1/README.md#filters-search-and-date-selection)
> and [chart modes](../phase-7.1/README.md#chart-modes).

Selected observations can be downloaded as:

- UTF-8 CSV (with a BOM so spreadsheet tooling decodes Persian headers)
- Excel workbook (`.xlsx`, right-to-left sheet view)

Charts can be downloaded as:

- Standalone interactive HTML (eager)
- PNG and SVG (on demand; disabled cleanly when Chromium is unavailable)

CSV and Excel exports include indicator metadata, units, timezone-aware
timestamps in ISO-8601 form, a Jalali display column, original values,
chain-linking flags, confidence, and source metadata.

## Static Chart Browser Setup

PNG and SVG exports use Plotly with Kaleido and a Chromium executable.

- If Google Chrome is installed in a standard location, no setup is needed.
- If Playwright's Chromium is installed, the dashboard discovers it in
  `~/.cache/ms-playwright`.
- To download Plotly's managed Chrome, run:

  ```bash
   poetry run plotly_get_chrome
   ```

- To use a specific executable, set:

   ```bash
   DASHBOARD_CHROME_PATH=/path/to/chrome
   ```

HTML exports do not require a browser.

## Data Quality Behavior

- Missing periods remain missing; the dashboard never interpolates by default.
- Quality panels report rows returned, expected observations, missing periods,
  observed start/end, chain-linked rows, and average confidence.
- Original and chain-linked values are preserved in Gold and exports.
- Catalog availability is displayed as **Unknown** when it is `NULL`.
- TGJU single-observation and sparse-history cases produce explicit warnings.

## Troubleshooting

### Database unavailable

```bash
make db-up
poetry run alembic upgrade head
make db-check
```

If Docker cannot connect, try:

```bash
DOCKER_CONTEXT=default make db-up
```

### No indicators or observations

Run a pipeline first. The dashboard intentionally does not invent catalog rows
or observations.

### PNG/SVG downloads fail

Set `DASHBOARD_CHROME_PATH` to a working Chromium executable. On systems where
the `chromium` command is a Snap wrapper, use the real Chrome/Chromium binary
or install Plotly's managed Chrome.

### Mixed-frequency correlation looks empty

This is expected when timestamps do not match exactly. Inspect the join-count
matrix; the dashboard does not forward-fill annual or daily values.

## Known Limitations

- TGJU is a current-price snapshot source, not a historical backfill.
- **Correction:** CPI **decile** data has existed since Phase 5 (the SCI
  connector loads ten expenditure-decile CPI series) and is surfaced on the
  Phase 7.1 Inflation page; it was never blocked on missing source data. The
  **monetary-domain** page remains deferred because no monetary indicators are
  loaded (CBI TSD is gated).
- The dashboard is local and single-user; it has no authentication or cloud
  deployment.
- Updates require rerunning the relevant ETL pipeline or Airflow DAG; the UI
  does not use real-time or WebSocket updates. The Phase 7.1 cache has no TTL or
  refresh control, so a pipeline run needs an app restart to appear.
