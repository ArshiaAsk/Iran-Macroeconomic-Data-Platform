# AGENTS.md

This file provides project-specific guidance to AI coding agents working in this repository.

## Project Overview

**Iran Macroeconomic Data Platform** is a comprehensive data engineering and analytics system that collects, processes, and visualizes 50+ years of Iran's macroeconomic indicators from 9+ heterogeneous sources (domestic and international).

The platform solves critical challenges for economic research:
- **Data fragmentation** across multiple incompatible sources
- **Base year discontinuities** requiring automated chain-linking
- **Frequency mismatches** from daily (FX, gold) to annual (World Bank) data
- **Technical barriers** with domestic sources lacking APIs
- **Data quality issues** from structural inflation and sanctions-related gaps

## Project Type

* **Type:** Data Engineering Platform + Analytics Dashboard (Hybrid)
* **Primary workflow:** Multi-source ETL → Time-series storage → Chain-linking transformations → Interactive dashboard
* **Lifecycle Stage:** Active implementation — Phase 1 (foundation) and Phase 2 (World Bank connector, ETL pipeline, chain-linking) complete; Phase 3 (TGJU scraper + Airflow) next

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Primary language for all components |
| PostgreSQL 15 + TimescaleDB | Time-series optimized data warehouse |
| SQLAlchemy 2.x | Typed ORM (`DeclarativeBase`, `Mapped`, `mapped_column`) |
| Playwright | Production-grade web scraping for domestic sources |
| Streamlit + Plotly | Interactive dashboard and visualization |
| Apache Airflow 3.x | Orchestration and scheduling (LocalExecutor) |
| Docker Compose | Local containerized environment |
| pytest + pytest-cov | Testing framework (target 80%+ coverage) |
| Poetry | Dependency management |
| ruff | Linting and formatting |
| mypy | Static type checking (strict mode) |
| Alembic | Database migrations |

> Airflow is pinned to **3.x** because it must share SQLAlchemy with the rest of
> the platform: Airflow 2.x requires `sqlalchemy<2.0`, which is incompatible with
> the 2.0 typed ORM used in `src/database/schema.py`.

## Commands

```bash
# Setup
make db-up                        # Start PostgreSQL + TimescaleDB
poetry install                    # Install dependencies

# Development
make format                       # Format code with ruff
make lint                         # Lint with ruff
make typecheck                    # Type check with mypy
make test                         # Run unit tests (skips integration)
make test-integration             # Run integration tests (requires Docker)
make test-all                     # Run unit + integration tests
make check                        # Run all quality gates (format + lint + typecheck + test)

# Database
poetry run alembic upgrade head            # Apply migrations
poetry run alembic revision --autogenerate # Create new migration
poetry run alembic check                   # Detect model/database drift

# Data Pipeline
poetry run python -m src.connectors.world_bank --dry-run  # Fetch + validate, write nothing
poetry run python -m src.connectors.world_bank            # Full Bronze → Silver → Gold run
airflow dags trigger <dag_id>        # Trigger specific DAG (Phase 3)

# Dashboard
streamlit run dashboard/app.py    # Launch interactive dashboard
```

Poetry 2.x has no built-in `shell`; prefix commands with `poetry run`. If Docker
commands fail with `Cannot connect to the Docker daemon`, prefix them with
`DOCKER_CONTEXT=default`.

## Project Structure

```text
iran-macro-platform/
├── src/
│   ├── connectors/          # Data source connectors (APIs + scrapers)
│   │   ├── base.py          # Abstract DataConnector protocol
│   │   ├── world_bank.py    # World Bank API connector ✓ IMPLEMENTED
│   │   └── ...              # imf.py, tgju_scraper.py, cbi_scraper.py — later phases
│   ├── etl/                 # Bronze/Silver/Gold transformations ✓ IMPLEMENTED
│   ├── chain_linking/       # Base year adjustment algorithms ✓ IMPLEMENTED
│   ├── database/            # Schema, connection, hypertable setup
│   └── utils/               # Validation, logging, configuration, retry
├── alembic/                 # Migration environment and versions
├── dashboard/               # Streamlit app — Phase 7
├── airflow/                 # DAG definitions — Phase 3
├── tests/
│   ├── unit/                # Unit tests for all modules
│   ├── integration/         # Integration tests (ETL + DB)
│   └── fixtures/            # Captured API payloads
├── docs/
│   ├── research/            # Research documents
│   ├── plans/               # Per-phase implementation plans
│   ├── phase-1/             # Phase 1 validation + implementation report
│   └── phase-2/             # Phase 2 Indicator catalog ✓ CREATED
├── scripts/                 # Utility scripts (init-db.sql)
├── docker-compose.yml       # Local infrastructure
├── pyproject.toml           # Poetry dependencies + tool configs
├── Makefile                 # Common commands
└── PRD.md                   # Product requirements document
```

## Data / ML Workflow

```text
┌─────────────────────────────────────────────────────────┐
│ DATA SOURCES (9+ heterogeneous sources)                 │
│ • APIs: World Bank, IMF, EIA, OPEC                     │
│ • Scraped: CBI TSD, SCI, TGJU                          │
│ • Packages: TSETMC (finpy-tse), HBSIR                  │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌───────────────────────▼─────────────────────────────────┐
│ CONNECTOR LAYER                                         │
│ • DataConnector protocol (connect, discover, fetch)    │
│ • Error handling: ConnectionError, DataRetrievalError  │
│ • Rate limiting, retries, user-agent rotation          │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌───────────────────────▼─────────────────────────────────┐
│ BRONZE LAYER (Raw Ingestion) — PostgreSQL              │
│ • Raw JSON from APIs                                    │
│ • Raw HTML from scrapers                                │
│ • Downloaded Excel/PDF files                            │
│ • Metadata: collection_timestamp, source, version       │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌───────────────────────▼─────────────────────────────────┐
│ SILVER LAYER (Cleaned) — PostgreSQL                    │
│ • Parsed and validated data                             │
│ • Null handling, outlier detection                      │
│ • Persian/Farsi number conversion                       │
│ • Date standardization (Persian → Gregorian)            │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌───────────────────────▼─────────────────────────────────┐
│ GOLD LAYER (Analysis-Ready) — TimescaleDB Hypertables  │
│ • Chain-linked continuous time series                   │
│ • Harmonized frequencies (daily/monthly/quarterly)      │
│ • Calculated indicators (MoM/YoY inflation, etc.)       │
│ • Indexed on (indicator_id, timestamp)                  │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌───────────────────────▼─────────────────────────────────┐
│ STREAMLIT DASHBOARD                                     │
│ • Domain-specific pages (Inflation, Monetary, FX, etc.) │
│ • Interactive Plotly charts                             │
│ • CSV/Excel export                                      │
│ • Data quality indicators                               │
└─────────────────────────────────────────────────────────┘
```

### Important Rules

* **Medallion Architecture:** All connectors MUST implement Bronze → Silver → Gold pattern
* **Chain-Linking First:** Any base year changes MUST be automatically chain-linked before Gold layer
* **Preserve Raw Data:** Always store raw responses in Bronze layer (allows re-parsing without re-scraping)
* **Audit Everything:** Log all transformations with lineage metadata (source, timestamp, transformation_type)
* **No Data Leakage:** When implementing forecasting, strictly enforce temporal splits
* **Frequency Handling:** Document frequency at ingestion; transformations must preserve temporal integrity
* **Persian Calendar:** Always convert Persian (Jalali) dates to Gregorian for storage; keep original in metadata

## Architecture

### Four-Layer Data Architecture (Medallion Pattern)

**Bronze Layer:**
- Raw data storage with minimal processing
- Immutable (never update, only append)
- Includes full HTTP responses, HTML, raw files
- Schema: `bronze_raw` with tables per source type

**Silver Layer:**
- Parsed, validated, and cleaned data
- Type conversions, null handling, outlier flagging
- Standardized schema across all sources
- Schema: `silver_cleaned` with unified time-series table

**Gold Layer:**
- Analysis-ready transformations
- Chain-linked time series with continuous base years
- Calculated fields (growth rates, moving averages)
- TimescaleDB hypertables for performance
- Schema: `gold_analytical` with fact tables

**Metadata Layer:**
- Indicator catalog (indicator_id, name, domain, unit, frequency, source)
- Data lineage tracking (collection_log, transformation_log, chain_linking_log)
- Data quality metrics (completeness, freshness, validation results)

### Connector Protocol

All data source connectors inherit from `DataConnector` abstract base class:

```python
class DataConnector(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to data source"""

    @abstractmethod
    def discover(self) -> list[IndicatorMetadata]:
        """Discover available indicators"""

    @abstractmethod
    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch time-series data"""

    @abstractmethod
    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """Validate fetched data"""
```

**Implementation pattern** (established by `src/connectors/world_bank.py`, the
reference implementation — copy it rather than redesigning):

```python
class MySourceConnector(DataConnector):
    def __init__(
        self,
        config: MySourceConfig | None = None,
        http_session: requests.Session | None = None,   # injected in tests
        retry_policy: RetryPolicy | None = None,        # injected in tests
        rate_limiter: RateLimiter | None = None,        # injected in tests
    ) -> None: ...
```

- **Inject the transport, `RetryPolicy`, and `RateLimiter`.** Unit tests pass a
  fake session plus no-op sleeps, so the whole suite runs with no network and no
  wall-clock cost. Real runs build them from configuration.
- **Own what you create.** `disconnect()` closes the session only when the
  connector created it; an injected session is the caller's to close. The class
  is a context manager, so `with Connector(...) as c:` cleans up.
- **`fetch()` returns a DataFrame and writes nothing.** Bronze needs the raw
  response too, so add a richer method (`fetch_series()` → a result object
  carrying `frame`, `raw_envelope`, `request_url`, `http_status_code`,
  `pages_fetched`, `source_last_updated`) and let the pipeline persist it. This
  keeps the connector testable without a database.
- **`discover()` describes indicators, not coverage.** Leave
  `availability_start` / `availability_end` as `None` when the source cannot
  report per-country coverage; the pipeline fills them from the observations it
  actually stored.
- **Config is a frozen dataclass with defaults from `get_config()`** — no
  hardcoded URLs, timeouts, or page sizes in the logic.
- **The pipeline runner is separate** (`src/etl/pipeline.py`) and uses one
  committed session per indicator, so one bad indicator cannot abort the batch.

### Orchestration

- **Daily Jobs:** High-frequency sources (TGJU, TSETMC) run at 11 PM Iran time
- **Weekly Jobs:** Medium-frequency sources (CBI, SCI) check for updates
- **Monthly Jobs:** API sources (World Bank, IMF) check for new releases
- **Backfill:** Separate DAGs for historical data collection

## Code Patterns

### Naming Conventions

- **Files/Modules:** Snake case (`world_bank.py`, `chain_linking.py`)
- **Classes:** Pascal case (`DataConnector`, `WorldBankConnector`)
- **Functions/Variables:** Snake case (`fetch_indicators`, `base_year`)
- **Constants:** Uppercase snake case (`MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private:** Leading underscore (`_parse_response`, `_validate_date_range`)
- **JSONB metadata columns:** the Python attribute is `record_metadata`, the
  database column is `metadata`. `metadata` is reserved by SQLAlchemy's
  `DeclarativeBase`, so declaring it directly raises `InvalidRequestError`.
  Always spell it:
  ```python
  record_metadata: Mapped[dict[str, Any] | None] = mapped_column(
      "metadata", JSONB, nullable=True
  )
  ```

### Database Conventions

- **Timezone-aware everywhere:** all `DateTime` columns use `timezone=True` and
  default to the `utc_now()` helper in `src/database/schema.py`. Never use
  `datetime.utcnow()` — it returns a naive datetime and `ruff` rejects it (DTZ).
- **Hypertable primary keys:** TimescaleDB requires the partitioning column in
  every unique index, so `GoldAnalytical` has a composite PK `(id, timestamp)`.
  Any future hypertable must include its time column in the PK.
- **Insert-time vs construction-time defaults:** `mapped_column(default=...)` is
  applied by the database on INSERT, not when you construct the object. A
  freshly-built instance still has `None` for those fields — assert against the
  declared default or flush the session first.
- **New migrations:** run `poetry run alembic check` after any model change; it
  fails if the models and database have drifted. TimescaleDB-managed indexes are
  excluded via the `include_object` hook in `alembic/env.py`, so add any new ones
  to `TIMESCALE_MANAGED_INDEXES` rather than letting them show up as spurious
  drops.

### File Organization

- **One connector per file:** `src/connectors/world_bank.py` contains `WorldBankConnector` class
- **Separation of concerns:** Parser logic separate from scraper logic (e.g., `tgju_scraper.py` + `tgju_parser.py`)
- **Shared utilities:** Extract common patterns to `src/utils/` (validation, retry logic, date conversion)
- **Test mirrors source:** `tests/unit/test_world_bank_connector.py` mirrors `src/connectors/world_bank.py`

### Configuration

- **Environment variables:** Use `.env` file for secrets (DB credentials, API keys)
- **Config classes:** Use Pydantic for typed configuration with validation
- **Per-connector config:** Each connector has config dataclass (e.g., `WorldBankConfig`)
- **No hardcoded values:** All URLs, timeouts, retry counts in config

### Error Handling & Logging

- **Custom exceptions:** Use hierarchy (`ConnectionError`, `DataRetrievalError`, `ValidationError`, `ParsingError`)
- **Structured logging:** Use Python `logging` with JSON formatting for Airflow
- **Retry logic:** Exponential backoff with jitter for transient failures
- **Graceful degradation:** Log warnings for partial failures, raise only for critical issues
- **Context propagation:** Include connector name, indicator_id, timestamp in all log messages

### Type Hints

- **Required:** All public functions must have type hints (enforced by mypy)
- **Return types:** Always specify return type, use `None` explicitly
- **Collections:** Use specific types (`List[str]`, `Dict[str, Any]`, not bare `list`, `dict`)
- **Optional:** Use `Optional[T]` for nullable values
- **Protocol:** Use `Protocol` for structural typing (e.g., `DataConnector`)

## Data & ML Conventions

### Data Quality Rules

- **Completeness:** Track null percentage per indicator; flag if >5%
- **Freshness:** Track `last_updated` timestamp; alert if staleness exceeds expected frequency
- **Consistency:** Validate that growth rates match when base years overlap (±1% tolerance)
- **Outliers:** Use IQR method for outlier detection; flag but don't drop (analyst decision)
- **Duplicates:** Reject duplicate (indicator_id, timestamp) pairs at Silver layer

### Chain-Linking Requirements

- **Overlap Period:** Require minimum 12 months overlap between base years for reliable chain-linking
- **Growth Rate Preservation:** Linked series must preserve YoY growth rates within ±1% during overlap
- **Confidence Scoring:** Assign confidence score based on overlap length and growth rate variance
- **Audit Trail:** Log every chain-linking operation with (original_value, linked_value, method, confidence)
- **Reversibility:** Store both original and linked values; never overwrite raw data

### Frequency Handling

- **Downsampling:** Daily → Monthly using end-of-month values (price data) or averages (volumes)
- **Upsampling:** Quarterly/Annual → Monthly using forward-fill (no interpolation to avoid artificial precision)
- **Interpolation:** Only when explicitly requested by analyst and clearly flagged in metadata
- **Alignment:** All monthly data aligned to month-end; quarterly to quarter-end

### Persian Calendar Conversion

- **Storage:** Always Gregorian in database
- **Display:** Show Persian calendar in dashboard when appropriate
- **Conversion:** Use `jdatetime` library for Persian ↔ Gregorian
- **Metadata:** Store original Persian date in metadata column when source provides it

## Testing & Validation

- **Test Command:** `make test` (runs pytest with coverage)
- **Test Location:** `tests/unit/` for unit tests, `tests/integration/` for integration tests
- **Coverage Target:** Minimum 80% code coverage (enforced in CI)

### Testing Patterns

**Unit Tests:**
- Mock all external dependencies (API calls, database, file system)
- Use `pytest.fixture` for shared test setup
- Test happy path + error cases + edge cases
- Fixture data in `tests/fixtures/` (JSON, CSV, HTML samples)

**Integration Tests:**
- Mark with `@pytest.mark.integration` (skipped by default)
- Require running PostgreSQL (Docker Compose)
- Test full Bronze → Silver → Gold flow
- Clean up database after each test

**Live API Tests:**
- Mark with `@pytest.mark.live` (skipped by default)
- Only run manually before releases
- Test against real APIs with small date ranges
- Document rate limits and quotas

**Scraper Tests:**
- Store sample HTML in fixtures
- Test parser separately from scraper
- Mock Playwright for scraper tests
- Test retry logic and error handling

### Validation Requirements

**Data Validation:**
- Schema validation at Silver layer (correct types, required fields)
- Range validation (e.g., inflation must be > -100%)
- Date validation (no future dates, reasonable historical range)
- Cross-validation (e.g., M2 ≥ M0)

**Connector Validation:**
- Must pass base protocol tests
- Must handle rate limiting gracefully
- Must log all errors with context
- Must store raw responses in Bronze

**Transform Validation:**
- Row counts match between layers
- No data loss during transformations
- Metadata preserved across layers
- Chain-linking preserves growth rates

## Key Files

| File | Purpose |
|------|---------|
| `PRD.md` | Product requirements and implementation plan |
| `docs/research/init-research.md` | Original research and data source analysis |
| `docs/phase-1/VALIDATION.md` | Phase 1 validation checklist with recorded results |
| `pyproject.toml` | Poetry dependencies, tool configs (ruff, mypy, pytest) |
| `docker-compose.yml` | PostgreSQL + TimescaleDB local setup |
| `Makefile` | Common commands (format, lint, test, check, db-*) |
| `src/connectors/base.py` | Abstract DataConnector protocol |
| `src/connectors/world_bank.py` | World Bank connector + `python -m` pipeline entry point (reference implementation) |
| `src/etl/bronze.py` | Raw envelope persistence + `DataCollectionLog` |
| `src/etl/silver.py` | Cleaning, outlier flagging, idempotent upsert |
| `src/etl/gold.py` | Chain-linked publication + derived growth series |
| `src/etl/lineage.py` | `TransformationLog` audit trail (records failures out of band) |
| `src/etl/pipeline.py` | Bronze → Silver → Gold runner, one session per indicator |
| `src/utils/retry.py` | Retry/backoff policy and rate limiter |
| `src/database/schema.py` | SQLAlchemy models for all layers |
| `src/database/connection.py` | Engine, session management, hypertable setup |
| `alembic/versions/20260817_1456_initial_schema.py` | Initial migration (all 4 schemas + hypertable) |
| `alembic/versions/20260819_1236_silver_unique_constraint.py` | `uq_silver_indicator_timestamp` (Silver idempotency) |
| `src/chain_linking/splice.py` | Chain-linking algorithm (break detection, splice, confidence) |
| `dashboard/app.py` | Streamlit entry point - *to be implemented (Phase 7)* |
| `docs/phase-2/data_dictionary.md` | Indicator catalog with coverage observed from a real run |

## Important Constraints

### Technical Constraints

- **Local-only deployment:** No cloud infrastructure; all services run via Docker Compose
- **Single-machine:** Must run on analyst's laptop (16GB RAM, 50GB disk minimum)
- **No real-time:** Daily updates sufficient; no streaming or real-time requirements
- **PostgreSQL only:** No additional databases or storage systems

### Data Constraints

- **Iran sanctions impact:** Some international sources may have gaps or delays for Iran data
- **Domestic source fragility:** CBI/SCI websites change structure frequently; scrapers must be maintainable
- **Publication delays:** Accept multi-month delays for domestic sources; dashboard shows last-updated timestamps
- **Base year changes:** Statistical agencies change base years unpredictably; chain-linking must be robust

### Development Constraints

- **Python-only:** No microservices, no separate frontend framework
- **Minimal infrastructure:** Avoid Kubernetes, complex orchestration, feature stores unless justified
- **Analyst-friendly:** Economists must be able to run system without DevOps expertise
- **Documentation-first:** Every connector must have usage examples and troubleshooting guide

### Scraping Constraints

- **Rate limiting:** Respect 1-2 requests per second; add delays between requests
- **Politeness:** Use proper User-Agent; don't overwhelm source websites
- **Failure tolerance:** Accept partial failures; alert but don't crash
- **Legal compliance:** Only scrape publicly available data; respect robots.txt

## On-Demand Context

| Topic | File |
|-------|------|
| Research & Data Sources | `docs/research/init-research.md` |
| Product Requirements | `PRD.md` |
| Loaded indicators, units, observed coverage | `docs/phase-2/data_dictionary.md` |
| Phase implementation plans | `docs/plans/` |

## Notes for AI Agents

### When Starting Implementation

1. **Begin with Phase 1:** Set up foundation (Docker, database schema, base connector protocol) before building connectors
2. **Follow PRD task order:** Start with World Bank (easy API) + TGJU (scraping) to validate architecture end-to-end
3. **Test incrementally:** Validate each layer (Bronze → Silver → Gold) before moving to next connector
4. **Document as you build:** Keep data dictionary and runbooks updated alongside code

### When Adding New Connectors

1. **Follow connector protocol:** Inherit from `DataConnector`, implement all abstract methods (connect, discover, fetch, validate)
2. **Copy the reference implementation:** `src/connectors/world_bank.py` — inject the session, `RetryPolicy`, and `RateLimiter` so unit tests need no network and no sleeps
3. **Bronze first:** Store raw responses before parsing (allows re-parsing without re-scraping)
4. **Test with fixtures:** Don't hit live APIs in unit tests; capture real payloads under `tests/fixtures/<source>/` and gate any live test behind `RUN_LIVE_API_TESTS=1` and `@pytest.mark.live()`
5. **Make re-runs idempotent:** Silver upserts on `(indicator_id, timestamp)`; Gold deletes and reinserts per indicator
6. **Document limitations:** Note data gaps, frequency, update schedules in docstrings, and add the indicators to `docs/phase-2/data_dictionary.md` with coverage observed from a real run
7. **Handle errors gracefully:** Use custom exception hierarchy (ConnectionError, DataRetrievalError, ValidationError)

### When Debugging Scrapers

1. **Check Bronze layer first:** Raw HTML may reveal parsing issues
2. **Validate selectors:** Website structure changes are most common failure
3. **Test retry logic:** Simulate failures to verify graceful degradation
4. **Check rate limiting:** Verify delays between requests are working

### When Working with Time Series

1. **Check frequency first:** Query indicator catalog for expected frequency
2. **Never interpolate by default:** Only fill forward or leave null unless explicitly requested
3. **Validate date ranges:** Check for future dates, unreasonable historical dates
4. **Preserve metadata:** Always track original source, collection date, transformations

### When Modifying Schema

1. **Use Alembic:** Never modify database directly; create migration
2. **Test migration:** Verify both upgrade and downgrade work
3. **Update models:** Keep SQLAlchemy models in sync with schema
4. **Document changes:** Explain why schema changed in migration docstring

### Common Pitfalls

- **Don't skip Bronze layer:** Always store raw responses, even for clean APIs
- **Don't hardcode dates:** Use dynamic date ranges based on indicator metadata
- **Don't assume frequency:** Check indicator catalog, don't assume monthly/annual
- **Don't drop outliers automatically:** Flag them, let analysts decide
- **Don't mix base years:** Always chain-link before combining multiple series
- **Don't forget Persian calendar:** Domestic sources often use Jalali dates
- **Don't name a column `metadata`:** it's reserved by SQLAlchemy — use
  `record_metadata` mapped to the `metadata` column (see Naming Conventions)
- **Don't pass raw SQL strings to `execute()`:** SQLAlchemy 2.0 requires
  `text("SELECT …")`
- **Don't register pool events on the `Pool` class:** bind them to the specific
  engine, or you mutate connection state for every engine in the process
- **Don't assert on `default=` values before flushing:** those defaults are
  applied by the database, not the constructor
