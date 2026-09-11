# Phase 7 Dashboard Runbook

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

## Filters And Exports

Domain pages support source, domain, frequency, indicator, and date filters.
Default date bounds come from observed catalog coverage, not hardcoded years.

Selected observations can be downloaded as:

- UTF-8 CSV
- Excel workbook (`.xlsx`)

Charts can be downloaded as:

- Standalone interactive HTML
- PNG
- SVG

CSV and Excel exports include indicator metadata, units, timezone-aware
timestamps in ISO-8601 form, original values, chain-linking flags, confidence,
and source metadata.

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
- CPI decile and monetary-domain pages are deferred until their source data
  is implemented in later phases.
- The dashboard is local and single-user; it has no authentication or cloud
  deployment.
- Updates require rerunning the relevant ETL pipeline or Airflow DAG; the UI
  does not use real-time or WebSocket updates.
