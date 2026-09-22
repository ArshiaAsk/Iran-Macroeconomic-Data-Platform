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
* **Lifecycle Stage:** Active implementation — Phases 1–7 complete; the Phase 7.1 dashboard refresh (Tasks 1–25) and the Phase 7.2 dashboard redesign (Waves 0–H) are implemented. Phase 4 added the generic pipeline runner plus the IMF (annual WEO, with forecasts) and EIA (monthly energy) API connectors. Phase 5 added the SCI domestic scraper (monthly CPI + quarterly unemployment, real 1395→1400 chain-linking) and its weekly DAG. Phase 6 added the two **package-backed** connectors — TSETMC (daily TEDPIX + `RET1D`/`MA30`/`.ME`) and HBSIR (weighted Gini, relative poverty, income deciles) — behind optional `tsetmc`/`hbsir` extras, plus a daily DAG. Phase 7.1 rebuilt the dashboard presentation: a `st.navigation` router + page registry, full Persian/RTL localization with a Jalali display policy, Market/Labor/Welfare pages, derived-series exposure with parent provenance, chain-linking transparency, correlation guardrails and catalog search (see `docs/phase-7.1/README.md`). Phase 7.2 rebuilt that presentation on a shared design system — vendored Vazirmatn, design tokens and a theme lock, scoped RTL CSS, and shared layout/KPI/section/filter/state components adopted by all ten pages under the D11 layout contract (see `docs/phase-7.2/README.md` and `docs/phase-7.2/design-system.md`). The OPEC basket, the **CBI TSD** scraper, and the TSETMC trading-value / market-P/E / market-cap portion of the Phase 6 scope are **deferred** — the first two sources block programmatic access, the last has no historical source in the package (see `docs/phase-4/VALIDATION.md`, `docs/phase-5/VALIDATION.md`, and `docs/phase-6/VALIDATION.md`). Phase 7.1 Tasks 27–28 (extended test suite + analyst acceptance pass), the cache-TTL item, and Phase 7.2's accepted deviations (F1 padding, F7 coverage-column wrap, the D3 Gregorian/Jalali bidi direction, and the unverified `<td title>` hover tooltip) are deferred. Phase 8 (production readiness) is implemented: GitHub Actions CI (static, unit matrix on 3.11/3.12, integration against the pinned `timescale/timescaledb:2.28.3-pg15` service), the pinned database image, the widened gate (`mypy src dashboard`, coverage over `src/` + `dashboard/`), a committed `poetry.lock`, `scripts/health_check.py`, the `pg_dump`/`pg_restore` backup/restore scripts with a tested roundtrip, `scripts/benchmark_queries.py` with a committed `docs/phase-8/benchmarks.json` baseline, and the architecture/runbook/troubleshooting documentation (`docs/architecture.md`, `docs/operations/`). The fresh-clone acceptance walkthrough and `docs/phase-8/VALIDATION.md` (Wave G), branch protection, and the LICENSE remain open

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
make format-check                 # Check formatting without rewriting (CI gate)
make lint                         # Lint with ruff
make typecheck                    # Type check src + dashboard with mypy
make test                         # Run unit tests (skips integration)
make test-integration             # Run integration tests (requires Docker)
make test-all                     # Run unit + integration tests
make check                        # Run all quality gates (format + lint + typecheck + test)

# Operations
make health                       # Report connector health and data freshness (exit 0/1/2)
make benchmark                    # Benchmark hot queries vs the committed baseline
make backup                       # Back up the database to backups/ (pg_dump -Fc)
make restore BACKUP_FILE=…        # Restore a backup into a scratch database

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
│   │   ├── world_bank.py    # World Bank API connector ✓ (reference implementation)
│   │   ├── imf.py           # IMF DataMapper connector (annual WEO + forecasts) ✓
│   │   ├── eia.py           # EIA Open Data v2 connector (monthly energy) ✓
│   │   ├── tgju_scraper.py  # TGJU Playwright scraper ✓
│   │   ├── tgju_parser.py   # TGJU HTML parser ✓
│   │   ├── sci_scraper.py   # SCI file scraper (Excel/PDF, Persian/Jalali) ✓
│   │   ├── sci_parser.py    # SCI workbook → Silver frame parser ✓
│   │   ├── tsetmc.py        # TSETMC connector (injectable client, TEDPIX + derivations) ✓
│   │   ├── tsetmc_parser.py # TSETMC indexB2 record → tidy daily frame ✓
│   │   ├── hbsir.py         # HBSIR connector (injectable loader, 12 welfare series) ✓
│   │   ├── hbsir_parser.py  # HBSIR weighted statistics (Gini, poverty, deciles) ✓
│   │   └── ...              # cbi_*.py — deferred (Phase 5 bot-defense gate closed)
│   ├── etl/                 # Bronze/Silver/Gold transformations ✓ IMPLEMENTED
│   ├── chain_linking/       # Base year adjustment algorithms ✓ IMPLEMENTED
│   ├── database/            # Schema, connection, hypertable setup
│   └── utils/               # Validation, logging, config, retry, period helpers ✓
├── alembic/                 # Migration environment and versions
├── dashboard/               # Streamlit app — Persian/RTL router (Phase 7.2) ✓
├── airflow/                 # DAG definitions — Phase 3
├── tests/
│   ├── unit/                # Unit tests for all modules
│   ├── integration/         # Integration tests (ETL + DB)
│   └── fixtures/            # Captured API payloads
├── docs/
│   ├── research/            # Research documents
│   ├── plans/               # Per-phase implementation plans
│   ├── architecture.md      # Architecture + data-flow document ✓
│   ├── operations/          # Runbook, troubleshooting guide, CI operations ✓
│   ├── phase-1/             # Phase 1 validation + implementation report
│   ├── phase-2/             # Indicator catalog (observed coverage)
│   ├── phase-3/             # TGJU scraper reports
│   ├── phase-4/             # IMF/EIA reports + OPEC gate record ✓
│   ├── phase-5/             # SCI reports + CBI gate record ✓
│   ├── phase-6/             # TSETMC/HBSIR reports + scope-narrowing record ✓
│   ├── phase-7/             # Dashboard runbook (historical) ✓
│   ├── phase-7.1/           # Dashboard refresh runbook + validation ✓
│   ├── phase-7.2/           # Dashboard redesign design system + validation ✓
│   └── phase-8/             # Production-readiness spike + benchmark baseline ✓
├── scripts/                 # init-db.sql + health/backup/restore/benchmark CLIs
├── docker-compose.yml       # Local infrastructure
├── pyproject.toml           # Poetry dependencies + tool configs
├── Makefile                 # Common commands
└── PRD.md                   # Product requirements document
```

## Data / ML Workflow

```text
┌─────────────────────────────────────────────────────────┐
│ DATA SOURCES (9+ heterogeneous sources)                 │
│ • APIs: World Bank, IMF, EIA (OPEC deferred)           │
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
- **New API sources plug into the generic runner.** `run_pipeline(connector,
  spec)` is driven by a `SourceSpec`: source name/type, frequency, derived-series
  namespace, per-indicator derivation overrides, forecast support, and the
  Bronze-row parser. Add a connector plus a `build_spec()` — do not fork the
  runner. World Bank remains a thin wrapper (`run_world_bank_pipeline`).
- **Forecasts are explicit and opt-in.** A source that legitimately stores
  future-dated periods (IMF WEO) sets `SourceSpec.supports_forecasts=True`;
  Silver then keeps those rows, counts them, and records `observation_type` in
  the row metadata. Every other source keeps rejecting future dates. The IMF
  `actual`/`estimate`/`forecast` label is an **explicit project convention**
  derived from the WEO vintage year — not an IMF-provided field.
- **Period and frequency maths live in shared helpers.** `src/utils/periods.py`
  provides `annual_period_end` / `month_period_end` / `parse_period` /
  `year_earlier` (month-end snapping makes monthly YoY exact across leap years);
  `src/etl/frequency.py` aggregates daily series to month-end. Do not
  re-implement period logic in a connector.
- **Secrets never reach Bronze or logs.** Build the persisted `request_url`
  without the API key and scrub it from error/retry text (see
  `src/connectors/eia.py`).

### Scraper-Specific Patterns (TGJU Reference)

For **web scrapers** (TGJU, CBI, SCI), the connector pattern differs from APIs:

**Bronze Structure for Scrapers:**
- Store **raw HTML** in Bronze `raw_data`, wrapped in the `{rows: [...]}` convention:
  ```python
  bronze.write_bronze(
      session,
      source_name="tgju",
      source_type="scraper",
      raw_envelope={
          "rows": [{"html": html_content, "url": request_url, "scraped_at": timestamp}]
      },
      ...
  )
  ```
- The `rows` wrapper allows `extract_rows()` to process scraped data uniformly
  with API responses. Even if a scraper produces **one observation** (TGJU
  current price), wrap it as a single-element list.

**Parser Separation:**
- Keep **scraper** (Playwright navigation) and **parser** (HTML extraction) in
  separate modules:
  - `tgju_scraper.py` — browser automation, page loading, retry logic
  - `tgju_parser.py` — HTML parsing, data extraction, validation
- This allows unit-testing the parser with fixture HTML (no browser needed).

**Persian/Farsi Data Handling:**
- **Persian digits** (`۰۱۲۳۴۵۶۷۸۹`) must be converted to Arabic numerals
  (`0123456789`) before parsing:
  ```python
  PERSIAN_TO_ARABIC = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
  cleaned = text.translate(PERSIAN_TO_ARABIC).replace(",", "")
  value = float(cleaned)
  ```
- **Persian dates** (Jalali calendar) must be converted to Gregorian for storage:
  ```python
  import jdatetime
  persian_date = jdatetime.datetime(1405, 6, 18)  # YYYY-MM-DD in Jalali
  gregorian = persian_date.togregorian()
  ```
- Store original Persian date in `metadata` for auditability.

**Single-Observation Sources (TGJU Reality):**
- TGJU provides **current price only**, not historical data. Each scrape produces:
  - 1 Bronze envelope (HTML)
  - 1 Silver observation (parsed price + timestamp)
  - 1 Gold level (no derived metrics from a single observation)
- **Time series are built by daily scraping**, not one backfill. A 30-day moving
  average requires 30 daily runs.
- Do not derive growth metrics (RET1D, MA7, MA30) until sufficient history exists.

**Playwright Usage:**
- Use **synchronous** Playwright API (`from playwright.sync_api import sync_playwright`)
  unless the connector genuinely needs async (most don't).
- Set `headless=True` for production, `headless=False` for debugging.
- Set page timeout to handle slow-loading domestic sites:
  ```python
  page.set_default_timeout(30_000)  # 30 seconds
  ```
- Rotate user-agents to avoid detection; store used agent in Bronze metadata.
- Close browser in `disconnect()` or `__exit__()` to avoid leaking processes.

**Testing Scrapers:**
- **Unit tests:** Mock Playwright with `FakePage`/`FakeBrowser` that return
  fixture HTML (see `tests/integration/test_tgju_pipeline.py` for reference).
- **Integration tests:** Use fixture HTML, not live scraping (brittle, slow).
- **Live tests:** Mark with `@pytest.mark.live` and skip by default. Gate behind
  `RUN_LIVE_API_TESTS=1` environment variable.

**Error Handling:**
- Domestic sites change structure frequently. When selectors break:
  1. Capture the new HTML as a fixture
  2. Update selectors in the parser
  3. Add regression test with old + new fixture
- Log the full HTML on parsing errors (but truncate in production logs).
- Use `ParsingError` for malformed HTML, `DataRetrievalError` for network issues.

### Orchestration

- **Daily Jobs:** High-frequency sources (TGJU, TSETMC) run at 11 PM Iran time
- **Weekly Jobs:** Medium-frequency sources (CBI, SCI) check for updates
- **Monthly Jobs:** API sources (World Bank, IMF) check for new releases
- **Backfill:** Separate DAGs for historical data collection

### Dashboard (Phase 7.1)

The Streamlit dashboard is Persian/RTL and is built on a strict layering. Keep
it that way when adding a page or a feature:

- **Router + registry, not implicit `pages/` discovery.** `dashboard/app.py` is
  the only entrypoint and calls `st.navigation`; `dashboard/navigation.py`
  declares the information architecture as data (`PageSpec` rows: `key`, `path`,
  `icon`, `group`, `domains`, `is_default`). Nav labels and in-page titles both
  resolve from the string catalog (`nav.<key>` / `page.<key>`). Domain ownership
  is declared once in `PAGES` and read by `page_for_domain()`; a new page must
  claim exactly the domains it renders. Page modules are thin delegates that call
  a `render_*` function in `dashboard/page_view.py` and must not call
  `st.set_page_config`.
- **Three presentation modules own the display layer:**
  - `dashboard/i18n.py` — every Persian UI-chrome string, keyed; `t()` raises on
    a missing key. One locale, no runtime switcher.
  - `dashboard/labels.py` — indicator/domain/source/frequency display names, the
    derived-suffix map, and the expected collection cadence map.
  - `dashboard/formatting.py` — Persian digits/separators, Jalali dates and
    periods, and the Tehran day-bounds constructors.
  No user-visible literal may live outside `i18n.py`, and no name map outside
  `labels.py`.
- **Display policy: `Asia/Tehran`, storage unchanged.** Timestamps are stored
  timezone-aware **UTC** and Gregorian. `Asia/Tehran` is applied only when a
  value is rendered or when a selected day is interpreted; `tehran_day_bounds` /
  `jalali_day_bounds` are the only bounds constructors. Period ends (UTC
  midnight) are stable; daily snapshot sources are not. The grid stays LTR.
- **Gold is the only analytical input.** The repository reads `gold_analytical`
  (LEFT JOIN `indicator_catalog`, with a second join on
  `record_metadata ->> 'derived_from'` for parent provenance). Derivedness is
  read from metadata, never from an id. Nothing is interpolated, forward-filled,
  resampled or normalized; chain-linking values are displayed as stored.
- **Absolute boundary:** dashboard work changes nothing under `src/`, `alembic/`
  or `airflow/`. If a dashboard feature seems to need an ETL change (e.g. IMF
  forecast labeling), it is a new phase, not a dashboard change.

### Dashboard UI conventions (Phase 7.2)

Phase 7.2 added the design system. These rules are enforced by tests and the plan
is at `docs/plans/phase-7.2-dashboard-redesign.md`; the reference is
`docs/phase-7.2/design-system.md`:

- **Layering is native → CSS → HTML (D6/D13).** Prefer a native Streamlit element
  themed by `.streamlit/config.toml`; only fall through when the layer above
  cannot express it. `st.html` strips `<svg>`, so a glyph is a CSS shape or an
  icon-font/Material glyph — never inline SVG.
- **The D11 layout contract.** A migrated page opens with `render_page_header`,
  renders KPI values through `render_kpi_band`, section titles through
  `render_section_header`, filters through `render_filter_bar`, and
  empty/error/loading through `dashboard/components/states.py`. It does **not**
  call raw `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` or pass
  `unsafe_allow_html` where a shared component exists.
  `tests/unit/dashboard/test_layout_guard.py` is the AST guard: it maps each
  migrated module to its migrated functions (`MIGRATED_PAGES`), and two
  completeness tests keep that map equal to reality (every registered page's
  delegate is listed; every render function in `page_view.py` is listed). Add a
  new render function to `MIGRATED_PAGES` or the guard fails.
- **Every user-visible string goes through `t()`.** `tests/unit/dashboard/test_literal_guard.py`
  fails on a literal passed to a Streamlit display function. Data-level English
  values (catalog names, source slugs) use its documented allowlist.
- **CSS lives only in `dashboard/components/direction.py`**, scoped by stable
  hooks (`data-testid`, `st-key-*`, `aria-current`) — never a hashed
  `st-emotion-cache-*` class. A new container that renders RTL text declares
  `direction: rtl`. New colours/radii/sizes are tokens in
  `dashboard/components/tokens.py`, read by the theme and the Plotly template.
- **Charts use the shared template** (`dashboard/components/charts.py`); the grid
  and the Plotly time axis stay LTR. Exports render PNG + SVG through
  `serialize_figure_images` (smoke: `test_exports.py -m integration`).
- **The dev-only screenshot script** (`scripts/dashboard_screenshots.py`) captures
  one PNG per registered page; it is **not** a CI gate. Restart the dev server
  before a capture set and record the commit under capture.
- **Gate per wave:** `make check` (whose `typecheck` target now covers `src/`
  **and** `dashboard/`) plus the ten-page router smoke
  (`tests/unit/dashboard/test_all_pages_smoke.py`).
- **Do not touch `src/`, `alembic/` or `airflow/` for a presentation change.**

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
| `src/connectors/imf.py` | IMF DataMapper connector (annual WEO + forecasts) |
| `src/connectors/imf_parser.py` | IMF payload → Silver frame parser (vintage-based observation labels) |
| `src/connectors/eia.py` | EIA Open Data v2 connector (monthly energy, API-key auth, paging) |
| `src/connectors/eia_parser.py` | EIA payload → Silver frame parser (string values, month-end) |
| `src/connectors/tgju_scraper.py` | TGJU scraper (Playwright + Persian handling) |
| `src/connectors/tgju_parser.py` | TGJU HTML parser (Persian digits, date conversion) |
| `src/connectors/sci_scraper.py` | SCI file scraper (Excel downloads, TLS pinning, `--dry-run` CLI) |
| `src/connectors/sci_parser.py` | SCI workbook → Silver frame parser (Jalali month-end) |
| `src/connectors/tsetmc.py` | TSETMC connector (injectable `finpy-tse` client, TEDPIX + `RET1D`/`MA30`/`.ME`) |
| `src/connectors/tsetmc_parser.py` | TSETMC cdn `indexB2` payload → tidy daily frame |
| `src/connectors/hbsir.py` | HBSIR connector (injectable `hbsir` loader, 12 weighted welfare series) |
| `src/connectors/hbsir_parser.py` | HBSIR weighted statistics (Gini, poverty rate, decile shares) |
| `src/utils/persian.py` | Shared Persian digits / prices / Jalali→Gregorian helpers |
| `src/etl/bronze.py` | Raw envelope persistence + `DataCollectionLog` |
| `src/etl/silver.py` | Cleaning, outlier flagging, idempotent upsert |
| `src/etl/gold.py` | Chain-linked publication + derived growth series |
| `src/etl/lineage.py` | `TransformationLog` audit trail (records failures out of band) |
| `src/etl/pipeline.py` | Generic Bronze → Silver → Gold runner (`SourceSpec`), one session per indicator |
| `src/etl/frequency.py` | Daily → month-end aggregation (last observation, no fill) |
| `src/utils/periods.py` | Annual/monthly period-end + exact prior-year alignment |
| `src/utils/retry.py` | Retry/backoff policy and rate limiter |
| `docs/phase-4/VALIDATION.md` | Phase 4 validation results + OPEC gate record |
| `docs/phase-5/VALIDATION.md` | Phase 5 SCI validation results + CBI gate record |
| `docs/phase-6/VALIDATION.md` | Phase 6 TSETMC/HBSIR validation results + TSETMC scope-narrowing record |
| `src/database/schema.py` | SQLAlchemy models for all layers |
| `src/database/connection.py` | Engine, session management, hypertable setup |
| `alembic/versions/20260817_1456_initial_schema.py` | Initial migration (all 4 schemas + hypertable) |
| `alembic/versions/20260819_1236_silver_unique_constraint.py` | `uq_silver_indicator_timestamp` (Silver idempotency) |
| `src/chain_linking/splice.py` | Chain-linking algorithm (break detection, splice, confidence) |
| `dashboard/app.py` | Streamlit entrypoint: shell + `st.navigation` router |
| `dashboard/navigation.py` | Page registry (`PageSpec`, `PAGES`, `page_for_domain`) — the IA/ownership declaration |
| `dashboard/i18n.py` | Persian UI string catalog + `t()` |
| `dashboard/labels.py` | Indicator/domain/source display names, derived-suffix map, cadence map |
| `dashboard/formatting.py` | Persian digits/separators, Jalali + `Asia/Tehran` display formatters |
| `dashboard/page_view.py` | Page composition (filters, Gold load, sections) |
| `dashboard/components/direction.py` | Scoped RTL CSS + Plotly typography template |
| `dashboard/components/tokens.py` | Design tokens (colours, radii, type scale) read by the theme and the Plotly template |
| `dashboard/components/layout.py` | Shared layout components (`render_page_header`, `render_kpi_band`, `render_section_header`, `render_filter_bar`) |
| `dashboard/repository.py` | Read-only SQL (LEFT JOIN catalog + parent provenance) |
| `docs/phase-7.1/README.md` | Dashboard refresh runbook (Persian page guide, Jalali policy, deferred scope) |
| `docs/phase-7.1/VALIDATION.md` | Phase 7.1 validation record + accepted deviations/gaps |
| `docs/phase-7.2/design-system.md` | Phase 7.2 tokens, theme mapping, component catalogue and D11 layout contract |
| `docs/phase-7.2/README.md` | Dashboard redesign runbook + validation status |
| `docs/phase-2/data_dictionary.md` | Indicator catalog with coverage observed from a real run |
| `docs/architecture.md` | Architecture + data-flow document (layers, DAGs, read path, timezone policy, limitations index) |
| `docs/operations/runbook.md` | Operational runbook (health, backup/restore, migrations, benchmarks) |
| `docs/operations/troubleshooting.md` | Troubleshooting guide (14 scenarios) |
| `docs/operations/ci.md` | CI jobs, required checks and branch protection |
| `scripts/health_check.py` | Read-only connector-health + data-freshness CLI (exit 0/1/2) |
| `scripts/backup_db.sh` / `scripts/restore_db.sh` | `pg_dump -Fc` backup and the documented TimescaleDB restore procedure |
| `scripts/benchmark_queries.py` | Hot-query benchmarks vs the committed `docs/phase-8/benchmarks.json` baseline |

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
| Phase 4 validation + OPEC gate decision | `docs/phase-4/VALIDATION.md` |
| Phase 5 SCI validation + CBI gate decision | `docs/phase-5/VALIDATION.md` |
| Phase 6 TSETMC/HBSIR validation + scope record | `docs/phase-6/VALIDATION.md` |
| Dashboard runbook (Persian pages, Jalali policy, deferred scope) | `docs/phase-7.1/README.md` |
| Dashboard refresh implementation notes | `docs/phase-7.1/IMPLEMENTATION.md` |
| Dashboard refresh validation + accepted deviations | `docs/phase-7.1/VALIDATION.md` |
| Dashboard redesign design system + D11 page contract | `docs/phase-7.2/design-system.md` |
| Dashboard redesign runbook + validation record | `docs/phase-7.2/README.md` |
| Architecture + data-flow (layers, DAGs, read path, timezone policy) | `docs/architecture.md` |
| Operations runbook (health, backup/restore, migrations, benchmarks) | `docs/operations/runbook.md` |
| Troubleshooting (14 scenarios) | `docs/operations/troubleshooting.md` |
| CI jobs, required checks and branch protection | `docs/operations/ci.md` |
| Phase 8 production-readiness plan | `docs/plans/phase-8-production-readiness.md` |
| Phase implementation plans | `docs/plans/` |

## Notes for AI Agents

### When Starting Implementation

1. **Begin with Phase 1:** Set up foundation (Docker, database schema, base connector protocol) before building connectors
2. **Follow PRD task order:** Start with World Bank (easy API) + TGJU (scraping) to validate architecture end-to-end
3. **Test incrementally:** Validate each layer (Bronze → Silver → Gold) before moving to next connector
4. **Document as you build:** Keep data dictionary and runbooks updated alongside code

### When Adding New Connectors

1. **Follow connector protocol:** Inherit from `DataConnector`, implement all abstract methods (connect, discover, fetch, validate)
2. **Copy the reference implementation:** `src/connectors/world_bank.py` — inject the session, `RetryPolicy`, and `RateLimiter` so unit tests need no network and no sleeps. `src/connectors/imf.py` (annual + forecasts) and `src/connectors/eia.py` (monthly + API key + paging) are worked examples of the same shape
3. **Add a `build_spec()`, not a runner:** describe the source with `SourceSpec` (frequency, derived prefix, per-indicator overrides, `supports_forecasts`, parser) and call `run_cli`/`run_pipeline`
4. **Bronze first:** Store raw responses before parsing (allows re-parsing without re-scraping). Use the `{"rows", "meta", "raw_response"}` envelope for API sources and `{"rows": [{"html", ...}]}` for scrapers
5. **Test with fixtures:** Don't hit live APIs in unit tests; capture real payloads under `tests/fixtures/<source>/` and gate any live test behind `RUN_LIVE_API_TESTS=1` and `@pytest.mark.live()`
6. **Make re-runs idempotent:** Silver upserts on `(indicator_id, timestamp)`; Gold deletes and reinserts per indicator
7. **Document limitations:** Note data gaps, frequency, update schedules in docstrings, and add the indicators to `docs/phase-2/data_dictionary.md` with coverage observed from a real run. If a source is blocked, do not work around it — record the evidence and defer
8. **Handle errors gracefully:** Use custom exception hierarchy (ConnectionError, DataRetrievalError, ValidationError); never let an API key reach Bronze or the logs

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
