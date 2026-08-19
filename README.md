# Iran Macroeconomic Data Platform

> A comprehensive data engineering and analytics platform for collecting, processing, and visualizing 50+ years of Iran's macroeconomic indicators from 9+ heterogeneous sources.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15](https://img.shields.io/badge/postgresql-15-blue.svg)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/timescaledb-latest-orange.svg)](https://www.timescale.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Overview

The Iran Macroeconomic Data Platform solves critical challenges for economic research on Iran:

- **Data fragmentation** across multiple incompatible sources (domestic and international)
- **Base year discontinuities** requiring automated chain-linking algorithms
- **Frequency mismatches** from daily (FX, gold) to annual (World Bank) data
- **Technical barriers** with domestic sources lacking APIs
- **Data quality issues** from structural inflation and sanctions-related gaps

### What It Does

- **Automated data collection** from 9+ sources (APIs + web scraping)
- **Bronze → Silver → Gold data pipeline** with chain-linking transformations
- **TimescaleDB-optimized storage** for 50+ years of time-series data
- **Interactive Streamlit dashboard** with domain-specific analytics
- **Publication-ready exports** (CSV, Excel) for research use

### Architecture

```text
Data Sources (APIs + Scrapers)
        ↓
  Connector Layer (DataConnector protocol)
        ↓
  Bronze Layer (Raw data - PostgreSQL)
        ↓
  Silver Layer (Cleaned data - PostgreSQL)
        ↓
  Gold Layer (Chain-linked - TimescaleDB)
        ↓
  Streamlit Dashboard (Interactive analytics)
```

---

## Prerequisites

### Required Software

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Docker** & **Docker Compose** — [Install Docker](https://docs.docker.com/get-docker/)
- **Poetry** — [Install Poetry](https://python-poetry.org/docs/#installation)
- **Git** — [Install Git](https://git-scm.com/downloads)

### System Requirements

- **RAM:** 16GB minimum (for PostgreSQL + TimescaleDB)
- **Disk:** 50GB free space (for time-series data)
- **OS:** Linux, macOS, or Windows with WSL2

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/iran-macro-platform.git
cd iran-macro-platform
```

### 2. Install Dependencies

```bash
# Install Python dependencies
poetry install
```

Poetry 2.x ships `shell` as a separate plugin, so prefix commands with
`poetry run` (e.g. `poetry run pytest`). To get the old behaviour:
`poetry self add poetry-plugin-shell`.

### 3. Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env with your configuration
# (Default values work for local development)
```

If a system PostgreSQL already occupies port 5432, set a free host port in
`.env` — the compose file honours it — and update `DATABASE_URL` to match:

```bash
DATABASE_PORT=5433
DATABASE_URL=postgresql://iran_macro:iran_macro_pass@localhost:5433/iran_macro_db
```

### 4. Start Database

```bash
# Start PostgreSQL + TimescaleDB
make db-up

# Wait for health check to pass
docker compose ps
```

If Docker Desktop is installed but not running, the CLI may target its stopped
socket and fail with `Cannot connect to the Docker daemon`. Use the system daemon
for a single command with `DOCKER_CONTEXT=default make db-up`.

### 5. Run Database Migrations

```bash
# Apply schema migrations
poetry run alembic upgrade head

# Verify tables created
make db-check
```

### 6. Run Tests

```bash
# Run full test suite
make test

# Run all quality gates
make check
```

### 7. Launch Dashboard (Phase 7)

```bash
# Start Streamlit dashboard
streamlit run dashboard/app.py
```

---

## Development Workflow

### Common Commands

```bash
# Code quality
make format       # Format code with ruff
make lint         # Lint with ruff
make typecheck    # Type check with mypy
make check        # Run all quality gates

# Testing
make test         # Unit tests with coverage (skips integration)
make test-unit    # Unit tests only
make test-integration  # Integration tests (requires Docker)
make test-all     # Unit + integration tests

# Database
make db-up        # Start Docker services
make db-down      # Stop Docker services
make db-shell     # Connect to PostgreSQL shell
make db-reset     # Reset database (WARNING: deletes data)
make db-check     # Verify connection + TimescaleDB extension

# Migrations
poetry run alembic revision --autogenerate -m "Description"  # Create migration
poetry run alembic upgrade head                              # Apply migrations
poetry run alembic downgrade -1                              # Rollback one migration
poetry run alembic check                                     # Detect model drift

# Data pipeline
poetry run python -m src.connectors.world_bank --dry-run  # Fetch + validate, write nothing
poetry run python -m src.connectors.world_bank            # Full Bronze → Silver → Gold run
airflow dags trigger <dag_id>                             # Trigger Airflow DAG (Phase 3)
```

### Project Structure

```text
iran-macro-platform/
├── src/
│   ├── connectors/          # Data source connectors (APIs + scrapers)
│   │   ├── base.py          # Abstract DataConnector base class
│   │   └── world_bank.py    # World Bank API connector + pipeline entry point
│   ├── etl/                 # Bronze/Silver/Gold transformations
│   │   ├── bronze.py        # Raw envelope persistence + collection log
│   │   ├── silver.py        # Cleaning, validation, idempotent upsert
│   │   ├── gold.py          # Chain-linked publication + derived growth
│   │   ├── lineage.py       # TransformationLog audit trail
│   │   └── pipeline.py      # Bronze → Silver → Gold runner
│   ├── chain_linking/       # Base year adjustment algorithms
│   │   └── splice.py        # Break detection, splice, confidence scoring
│   ├── database/            # Schema and connection management
│   └── utils/               # Config, logging, validation, retry/backoff
├── alembic/                 # Migration environment and versions
├── dashboard/               # Streamlit app (Phase 7 — not built yet)
├── airflow/                 # DAG definitions (Phase 3 — not built yet)
├── tests/
│   ├── unit/                # Unit tests (no network, no database)
│   ├── integration/         # Integration tests (PostgreSQL + TimescaleDB)
│   └── fixtures/            # Captured API payloads
├── docs/
│   ├── research/            # Research documents
│   ├── plans/               # Phase implementation plans
│   ├── phase-1/             # Phase 1 validation + implementation report
│   └── phase-2/             # Phase 2 Indicator catalog (observed coverage)
├── scripts/                 # Utility scripts (init-db.sql)
├── docker-compose.yml       # Local infrastructure
├── pyproject.toml           # Poetry dependencies
├── Makefile                 # Common commands
├── AGENTS.md                # AI agent guidance
└── PRD.md                   # Product requirements
```

### Adding a New Data Connector

1. **Inherit from `DataConnector`:**

```python
from datetime import datetime

import pandas as pd

from src.connectors.base import DataConnector, IndicatorMetadata
from src.utils.validation import ValidationResult


class MySourceConnector(DataConnector):
    def connect(self) -> bool:
        """Cheap reachability probe — True if the source is usable."""

    def discover(self) -> list[IndicatorMetadata]:
        """Describe the available indicators for the catalog."""

    def fetch(
        self, indicator_id: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Return a tidy frame; write nothing to the database."""

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """Report quality; warn on gaps rather than dropping rows."""
```

2. **Inject the HTTP session, `RetryPolicy`, and `RateLimiter`** so tests can
   serve captured payloads with no network and no sleeps
3. **Store the raw response in the Bronze layer** via `src.etl.bronze`, then run
   `src.etl.silver` and `src.etl.gold`
4. **Add unit tests with captured fixtures** under `tests/fixtures/<source>/`
5. **Document in `docs/phase-2/data_dictionary.md`** with coverage observed from a real
   run

`src/connectors/world_bank.py` is the reference implementation; see `AGENTS.md`
for the detailed conventions.

---

## Data Sources

| Source | Type | Indicators | Frequency | Status |
|--------|------|------------|-----------|--------|
| **World Bank** | API | GDP, inflation, trade, population, energy (12 indicators) | Annual | ✅ Implemented (Phase 2) |
| **IMF DataMapper** | API | Fiscal, External | Quarterly | Planned (Phase 4) |
| **CBI TSD** | Scraper | Monetary, Banking | Monthly | Planned (Phase 5) |
| **TGJU** | Scraper | FX, Gold | Daily | Planned (Phase 3) |
| **SCI** | Scraper | CPI, Labor | Quarterly | Planned (Phase 5) |
| **TSETMC** | Package | Stock indices | Daily | Planned (Phase 6) |
| **EIA** | API | Oil prices | Daily | Planned (Phase 4) |
| **OPEC** | Scraper | Oil production | Monthly | Planned (Phase 4) |
| **HBSIR** | Package | Household surveys | Annual | Planned (Phase 6) |

Phase numbers follow `PRD.md` §7. Every World Bank indicator, its unit, and its
**observed** coverage for Iran are documented in
[docs/phase-2/data_dictionary.md](docs/phase-2/data_dictionary.md).

---

## Testing

### Running Tests

```bash
# Unit tests with coverage (the default gate; skips integration)
make test

# Integration tests (requires Docker)
make test-integration

# Everything
make test-all

# Live API tests (manual only — hits the real World Bank API)
RUN_LIVE_API_TESTS=1 poetry run pytest -m live
```

Current status: **253 tests passing** — 225 unit (86.94% coverage) and 28
integration (93.61% combined). The live API test is skipped unless
`RUN_LIVE_API_TESTS=1` is set.

### Coverage Requirements

- **Minimum:** 80% code coverage (enforced by `make test` and `make test-all`)
- **Target:** 90%+ for core utilities and connectors

`make test-integration` runs with the gate disabled — the 80% threshold measures
the project as a whole, so an integration-only subset cannot meaningfully satisfy
it.

### Test Organization

- **Unit tests:** Mock all external dependencies
- **Integration tests:** Test full Bronze → Silver → Gold flow
- **Fixtures:** Sample data in `tests/fixtures/`
- **Live tests:** Skipped by default, run manually before releases

---

## Documentation

### Key Documents

- **[AGENTS.md](AGENTS.md)** — Project conventions and AI agent guidance
- **[PRD.md](PRD.md)** — Product requirements and implementation plan
- **[docs/research/init-research.md](docs/research/init-research.md)** — Data source analysis
- **[docs/phase-2/data_dictionary.md](docs/phase-2/data_dictionary.md)** — Indicator catalog with observed coverage
- **[docs/phase-1/VALIDATION.md](docs/phase-1/VALIDATION.md)** — Phase 1 validation checklist
- **[docs/plans/](docs/plans/)** — Per-phase implementation plans

### Architecture Principles

1. **Medallion Architecture:** Bronze (raw) → Silver (cleaned) → Gold (analysis-ready)
2. **Chain-Linking First:** Automatically handle base year changes before Gold layer
3. **Preserve Raw Data:** Always store raw responses (allows re-parsing without re-scraping)
4. **Audit Everything:** Log all transformations with lineage metadata
5. **No Data Leakage:** Enforce temporal splits for forecasting models

---

## Troubleshooting

### Docker Issues

```bash
# Check container status
docker compose ps

# View logs
docker compose logs postgres

# Reset Docker environment
make db-down
docker compose down -v
make db-up
```

If every `docker` command fails with `Cannot connect to the Docker daemon`,
check `docker context ls` — a stopped Docker Desktop leaves the CLI pointed at
its socket. Prefix with `DOCKER_CONTEXT=default` to use the system daemon.

### Database Connection Issues

```bash
# Test connection
docker compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT version();"

# Check TimescaleDB extension
docker compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT * FROM timescaledb_information.hypertables;"
```

### Poetry Issues

```bash
# Update lock file
poetry lock --no-update

# Install specific version
poetry add package@^1.0.0

# Clear cache
poetry cache clear . --all
```

---

## Roadmap

### Phase 1: Foundation ✅
- [x] Project scaffolding with Poetry
- [x] Docker Compose with PostgreSQL + TimescaleDB
- [x] Database schema (Bronze/Silver/Gold/Metadata)
- [x] DataConnector protocol and testing framework

### Phase 2: API Connector MVP ✅ (Current)
- [x] World Bank API connector (12 indicators, retry/backoff, discovery)
- [x] Bronze → Silver → Gold pipeline with lineage logging
- [x] Chain-linking algorithm (break detection, splice, confidence scoring)
- [x] 66 years of Iran macroeconomic data queryable from Gold
- [x] Data dictionary recorded from a real run

### Phase 3: Web Scraper MVP + Orchestration (Week 3-4)
- [ ] Playwright TGJU scraper (FX + gold prices)
- [ ] Airflow local deployment and daily update DAGs
- [ ] Error monitoring and alerts

### Phase 4: Additional APIs (Week 4-5)
- [ ] IMF DataMapper connector with forecasts
- [ ] EIA and OPEC energy connectors

### Phase 5: Complex Domestic Scrapers (Week 5-6)
- [ ] CBI TSD monetary scraper
- [ ] SCI CPI/labour scraper with real multi-base-year chain-linking

### Phase 6: Market & Survey Data (Week 6-7)
- [ ] TSETMC stock market connector
- [ ] HBSIR household survey connector

### Phase 7: Dashboard (Week 7-8)
- [ ] Streamlit multi-page app
- [ ] Domain-specific analytics
- [ ] Export functionality

### Phase 8: Production Readiness (Week 8)
- [ ] CI/CD pipeline
- [ ] Backup automation
- [ ] Performance optimization

---

## Contributing

This is a research project. Contributions are welcome for:

- New data source connectors
- Chain-linking algorithm improvements
- Dashboard features
- Documentation enhancements

See `AGENTS.md` for code conventions and patterns.

---

## License

[To be determined — see LICENSE file]

---

## Acknowledgments

- TimescaleDB for time-series optimizations
- finpy-tse for TSETMC integration
- World Bank and IMF for open data APIs
- TGJU for public FX/gold price data

---

## Contact

For questions or issues, please open a GitHub issue.

**Maintainer:** [Your Name]  
**Project Status:** Phase 2 API Connector MVP complete — Phase 3 (TGJU scraper + Airflow) next
