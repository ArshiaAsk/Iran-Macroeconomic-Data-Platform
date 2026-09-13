# Phase 5: Complex Domestic Scrapers (SCI + CBI)

**Status:** ✅ Complete for the committed scope — SCI implemented end to end;
**CBI deferred** (source blocks programmatic access).
**Completed:** September 13, 2026
**Plan:** [phase-5-cbi-sci-scrapers.md](../plans/phase-5-cbi-sci-scrapers.md)

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Task-by-task architecture notes, deviations | Developers |
| **[VALIDATION.md](VALIDATION.md)** | Reconnaissance, CBI gate evidence, live-run results | QA, Maintainers |
| **[data_dictionary.md](../phase-2/data_dictionary.md#sci-indicators-phase-5)** | Observed SCI coverage (Phase 5 section) | Analysts |
| **[cbi gate fixture](../../tests/fixtures/cbi/_gate_task7.json)** | Machine-readable CBI probe result | QA |

---

## What Was Built

### Components

- ✅ **Persian text helpers** (`src/utils/persian.py`) — Persian/Arabic-Indic
  digits, separators, `parse_price`, Jalali→Gregorian conversion (shared with
  TGJU).
- ✅ **SCI parser** (`src/connectors/sci_parser.py`) — Excel (`.xlsx` via
  openpyxl, legacy `.xls` via xlrd) into a tidy month-end frame; `ParsingError`
  on unknown layouts.
- ✅ **SCI scraper/connector** (`src/connectors/sci_scraper.py`) — file
  downloads with retries, rate limiting, size guard, SHA-256 provenance, and a
  pinned CA bundle (the site serves an incomplete TLS chain).
- ✅ **Gold multi-segment chain-linking** (`src/etl/gold.py`) —
  `silver_to_gold(..., segment_indicator_ids=[...])` orders base-year segments
  oldest-first and splices them into one canonical series.
- ✅ **Runner/catalog wiring** — `discover()` seeds canonical CPI ids active and
  `B<year>` segments inactive; canonicals are chain-linked only after every
  segment is persisted (new `IndicatorOutcome.series_ids`).
- ✅ **Weekly DAG** (`airflow/dags/sci_weekly.py`) — Fridays 03:00
  `Asia/Tehran`, no logic in the DAG.
- ⛔ **CBI** — evaluated, blocked by an F5 JavaScript challenge / unreachable
  TSD host, not implemented.

### Sources

| Source | Frequency | Indicators | Coverage (observed) |
|--------|-----------|-----------:|---------------------|
| SCI CPI (national/urban/rural) | Monthly | 3 canonical (urban chain-linked) | Urban 1982-03 … 2026-07; national 2011-03 … 2026-07; rural 1982-05 … 2026-07 |
| SCI CPI deciles | Monthly | 10 | 2016-03 … 2026-07 |
| SCI unemployment (LFS) | Quarterly | 1 | 2026-05 (spring 1405, 9.1%) |
| CBI TSD | — | 0 | Deferred — bot defense blocks access |

### Tests

- **Unit:** 648 passed + 1 gated live-skipped, 86.83% coverage (parser,
  scraper, multi-segment Gold, Persian helpers, DAG import).
- **Integration:** 86 passed, 4 live-skipped (90 collected) across the SCI,
  World Bank, TGJU, IMF, EIA, database, and dashboard suites.
- **Quality gates:** `mypy src/` clean; `ruff check` / `ruff format --check`
  clean.

---

## Quick Start

### Prerequisites

```bash
poetry install                 # pulls pdfplumber + xlrd for SCI workbooks
make db-up
poetry run alembic upgrade head
```

### Run the pipeline

```bash
# Fetch + parse + validate, write nothing
poetry run python -m src.connectors.sci_scraper --dry-run

# Full Bronze → Silver → Gold (chain-links the canonical CPI series)
poetry run python -m src.connectors.sci_scraper

# One publication (slug or series id)
poetry run python -m src.connectors.sci_scraper --indicators cpi_urban
```

The CLI accepts `--log-level`. Bronze is append-only: re-running adds envelopes
and refreshes Silver (upsert) and Gold (delete-and-reinsert).

### Schedule it

```bash
make airflow-up            # loads airflow/dags/sci_weekly.py
poetry run airflow dags trigger sci_weekly
```

### Run the tests

```bash
poetry run pytest tests/unit -q --no-cov
poetry run pytest tests/integration/test_sci_pipeline.py -m integration -q --cov-fail-under=0
```

Live tests (real SCI downloads) are gated:

```bash
RUN_LIVE_API_TESTS=1 poetry run pytest -m live
```

---

## Notes and limitations

- **Only two CPI bases are published** (1395 = 2016, 1400 = 2021), so only the
  urban series is genuinely chain-linked; national/rural are passthroughs.
- **The 1395 base reaches back to 1361-01 (1982-03-31)** via the tidy
  `جدول 3` sheet, so the splice rescales 240 observations onto the 1400 base
  (251-month overlap, confidence 0.9985).
- **`ChainLinkingLog.base_year_from`/`base_year_to`** currently record the
  splice's overlap-boundary years (2023/2002), not the nominal bases
  (2016/2021). The catalog and segment ids carry the nominal bases correctly;
  the log field is a **known pre-existing defect** flagged in the data
  dictionary.
- **CBI is not ingested**; evidence and rationale are in
  [VALIDATION.md](VALIDATION.md#task-6--cbi-parser-gate-re-check).
- **Unemployment is a single observation per run**; the series grows with
  periodic weekly runs, not a backfill.
