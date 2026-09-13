# Phase 4: Additional API Connectors

**Status:** ✅ Complete for the committed scope — IMF and EIA implemented; OPEC
deferred (source blocked).
**Completed:** September 12, 2026
**Plan:** [phase-4-additional-api-connectors.md](../plans/phase-4-additional-api-connectors.md)

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Architecture changes, components, deviations | Developers |
| **[VALIDATION.md](VALIDATION.md)** | Live API findings, test results, OPEC gate record | QA, Maintainers |
| **[data_dictionary.md](../phase-2/data_dictionary.md#imf-indicators-phase-4)** | Observed coverage for IMF/EIA (Phase 4 sections) | Analysts |

---

## What Was Built

### Components

- ✅ **Generic pipeline runner** (`src/etl/pipeline.py`) — `SourceSpec` /
  `FetchResult` / `run_pipeline`; World Bank is now a thin wrapper.
- ✅ **Shared period helpers** (`src/utils/periods.py`) — annual/monthly
  period-end and exact prior-year alignment.
- ✅ **Frequency utilities** (`src/etl/frequency.py`) — daily → month-end
  aggregation (used by the deferred OPEC path).
- ✅ **Forecast-aware Silver** — future-dated IMF WEO periods are retained and
  labelled, not rejected.
- ✅ **Frequency-aware YoY** — `.YOY` is a true prior-period comparison.
- ✅ **IMF connector + parser** (`src/connectors/imf.py`, `imf_parser.py`).
- ✅ **EIA connector + parser** (`src/connectors/eia.py`, `eia_parser.py`).
- ⛔ **OPEC basket** — evaluated, blocked by Cloudflare, not implemented.

### Sources

| Source | Frequency | Indicators | Coverage (observed) |
|--------|-----------|-----------:|---------------------|
| IMF DataMapper (WEO April 2026) | Annual | 6 | Iran 1980–2031 (LUR 1990–2031), incl. 5 forecast years |
| EIA Open Data v2 | Monthly | 2 | 2024-01 … present (fixture-verified to 2026-05; live run pending a key) |
| OPEC basket | — | 0 | Deferred — source blocks programmatic access |

### Tests

- **Unit:** 496 passed, 87.51% coverage (IMF 42, EIA 48, plus shared ETL/utils).
- **Integration:** 73 passed, 3 live-skipped (World Bank, TGJU, IMF, EIA).
- **Quality gates:** `mypy src/` clean; `ruff check` / `ruff format --check`
  clean.

---

## Quick Start

### Prerequisites

```bash
poetry install
make db-up
poetry run alembic upgrade head
```

### Run the pipelines

```bash
# IMF — no key required
poetry run python -m src.connectors.imf --dry-run   # fetch + report, no writes
poetry run python -m src.connectors.imf             # full Bronze → Silver → Gold

# EIA — requires a free key (https://www.eia.gov/opendata/register.php)
EIA_API_KEY=<your key> poetry run python -m src.connectors.eia --dry-run
EIA_API_KEY=<your key> poetry run python -m src.connectors.eia
```

Both CLIs accept `--indicators CODE1,CODE2` and `--log-level`.

### Run the tests

```bash
poetry run pytest tests/unit -q                          # fast, no network/DB
poetry run pytest tests/integration -m integration -q    # requires Docker
```

Live tests (real API) are gated:

```bash
RUN_LIVE_API_TESTS=1 poetry run pytest -m live
```

---

## Notes and limitations

- **IMF actual/estimate/forecast** is a **project convention** derived from the
  WEO vintage year — not an IMF-provided field. See the data dictionary.
- **EIA** requires `EIA_API_KEY`; a missing, placeholder, or invalid key aborts
  the run once, before any layer is written. The key never reaches Bronze or the
  logs.
- **OPEC** is not ingested; evidence and rationale are in
  [VALIDATION.md](VALIDATION.md#opec-basket-gate-task-1213--blocked-not-implemented).
- No new Airflow DAGs were added in Phase 4; scheduling the monthly annual/API
  cadence is a follow-up.
