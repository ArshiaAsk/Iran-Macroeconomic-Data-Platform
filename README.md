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

# Activate virtual environment
poetry shell
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env with your configuration
# (Default values work for local development)
```

### 4. Start Database

```bash
# Start PostgreSQL + TimescaleDB
make db-up

# Wait for health check to pass
docker-compose ps
```

### 5. Run Database Migrations

```bash
# Apply schema migrations
alembic upgrade head

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
make test         # Run pytest with coverage
make test-unit    # Unit tests only
make test-integration  # Integration tests (requires Docker)

# Database
make db-up        # Start Docker services
make db-down      # Stop Docker services
make db-shell     # Connect to PostgreSQL shell
make db-reset     # Reset database (WARNING: deletes data)

# Migrations
alembic revision --autogenerate -m "Description"  # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one migration

# Data pipeline (Phase 3+)
python -m src.connectors.world_bank               # Run World Bank connector
airflow dags trigger <dag_id>                     # Trigger Airflow DAG
```

### Project Structure

```text
iran-macro-platform/
├── src/
│   ├── connectors/          # Data source connectors (APIs + scrapers)
│   │   ├── base.py          # Abstract DataConnector protocol
│   │   ├── world_bank.py    # World Bank API connector
│   │   ├── imf.py           # IMF DataMapper connector
│   │   ├── tgju_scraper.py  # TGJU FX/gold scraper
│   │   └── cbi_scraper.py   # CBI TSD monetary data scraper
│   ├── etl/                 # Bronze/Silver/Gold transformations
│   ├── chain_linking/       # Base year adjustment algorithms
│   ├── database/            # Schema, migrations, query utilities
│   └── utils/               # Validation, logging, configuration
├── dashboard/
│   ├── app.py               # Streamlit entry point
│   ├── pages/               # Multi-page dashboard
│   └── components/          # Reusable UI components
├── airflow/
│   ├── dags/                # DAG definitions
│   └── config/              # Airflow configuration
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── fixtures/            # Test data
├── docs/
│   ├── research/            # Research documents
│   ├── architecture.md      # System architecture
│   └── data_dictionary.md   # Indicator catalog
├── scripts/                 # Utility scripts
├── docker-compose.yml       # Local infrastructure
├── pyproject.toml           # Poetry dependencies
├── Makefile                 # Common commands
├── AGENTS.md                # AI agent guidance
└── PRD.md                   # Product requirements
```

### Adding a New Data Connector

1. **Inherit from `DataConnector`:**

```python
from src.connectors.base import DataConnector

class MySourceConnector(DataConnector):
    def connect(self) -> bool:
        # Establish connection
        pass
    
    def discover(self) -> List[IndicatorMetadata]:
        # Discover available indicators
        pass
    
    def fetch(self, indicator_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        # Fetch time-series data
        pass
    
    def validate(self, data: pd.DataFrame) -> ValidationResult:
        # Validate fetched data
        pass
```

2. **Store raw data in Bronze layer**
3. **Add tests with mocked responses**
4. **Document in `docs/data_dictionary.md`**

See `AGENTS.md` for detailed connector implementation guidelines.

---

## Data Sources

| Source | Type | Indicators | Frequency | Status |
|--------|------|------------|-----------|--------|
| **World Bank** | API | GDP, Trade, Inflation | Annual | ✓ Implemented |
| **IMF DataMapper** | API | Fiscal, External | Quarterly | Planned (Phase 2) |
| **CBI TSD** | Scraper | Monetary, Banking | Monthly | Planned (Phase 2) |
| **TGJU** | Scraper | FX, Gold | Daily | Planned (Phase 2) |
| **SCI** | Scraper | CPI, Labor | Quarterly | Planned (Phase 4) |
| **TSETMC** | Package | Stock indices | Daily | Planned (Phase 5) |
| **EIA** | API | Oil prices | Daily | Planned (Phase 5) |
| **OPEC** | Scraper | Oil production | Monthly | Planned (Phase 6) |
| **HBSIR** | Package | Household surveys | Annual | Planned (Phase 6) |

---

## Testing

### Running Tests

```bash
# All tests with coverage
make test

# Unit tests only
pytest tests/unit/

# Integration tests (requires Docker)
pytest tests/integration/ -m integration

# Live API tests (manual only)
pytest tests/integration/ -m live
```

### Coverage Requirements

- **Minimum:** 80% code coverage (enforced)
- **Target:** 90%+ for core utilities and connectors

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
- **[docs/architecture.md](docs/architecture.md)** — System architecture (Phase 2)
- **[docs/data_dictionary.md](docs/data_dictionary.md)** — Indicator catalog (Phase 2)

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
docker-compose ps

# View logs
docker-compose logs postgres

# Reset Docker environment
make db-down
docker-compose down -v
make db-up
```

### Database Connection Issues

```bash
# Test connection
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT version();"

# Check TimescaleDB extension
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT * FROM timescaledb_information.hypertables;"
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

### Phase 1: Foundation ✅ (Current)
- [x] Project scaffolding with Poetry
- [x] Docker Compose with PostgreSQL + TimescaleDB
- [x] Database schema (Bronze/Silver/Gold/Metadata)
- [x] DataConnector protocol and testing framework

### Phase 2: Core Connectors (Week 3-4)
- [ ] World Bank API connector
- [ ] TGJU scraper (FX + gold prices)
- [ ] End-to-end Bronze → Silver → Gold validation

### Phase 3: Orchestration (Week 5)
- [ ] Airflow local deployment
- [ ] Daily update DAGs
- [ ] Error monitoring and alerts

### Phase 4-6: Connector Expansion (Week 6-8)
- [ ] All 9 data sources integrated
- [ ] Chain-linking algorithm implemented
- [ ] Data quality monitoring

### Phase 7: Dashboard (Week 9-10)
- [ ] Streamlit multi-page app
- [ ] Domain-specific analytics
- [ ] Export functionality

### Phase 8: Production Readiness (Week 11-12)
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
**Project Status:** Phase 1 Foundation (In Development)
