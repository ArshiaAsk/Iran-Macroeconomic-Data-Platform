# Implementation Plan — Iran Macroeconomic Data Platform

## 1. Problem Statement

Data analysts and economists studying Iran's macroeconomy face critical challenges:

* **Data Fragmentation:** Economic indicators are scattered across 9+ domestic and international sources with no unified access.
* **Technical Barriers:** Domestic sources (CBI, SCI) lack APIs, requiring complex web scraping.
* **Data Quality Issues:** Base-year changes create discontinuities in historical time series.
* **Frequency Mismatches:** Data ranges from daily (FX, gold) to annual (World Bank), requiring sophisticated resampling.
* **Publication Delays:** Domestic sources have multi-month lags; international sources have 1–2 year delays.

The project aims to build a local Python-based data platform that automates collection, cleaning, chain-linking, and visualization of Iran's macroeconomic indicators for economic analysis and research.

---

## 2. Requirements

### 2.1 User Requirements

* **Primary User:** Data analysts and economists conducting macroeconomic research.
* **Core Need:** Interactive dashboard for exploring 50+ years of economic trends across 9 analytical domains.
* **Key Use Cases:**

  * Track inflation trends across income deciles.
  * Analyze monetary policy impacts on exchange rates and gold prices.
  * Compare domestic GDP growth with international forecasts.
  * Generate publication-ready charts and export clean datasets.

### 2.2 Technical Requirements

* **Stack:** Python-focused (ETL, analytics, dashboard).
* **Storage:** PostgreSQL with time-series optimizations.
* **Deployment:** Local development using Docker Compose.
* **Data Freshness:** Daily automated updates for high-frequency sources.
* **Scraping:** Production-grade with error recovery and anti-detection.
* **Base Year Handling:** Fully automated chain-linking with audit logs.

### 2.3 Data Requirements

* **9 Analytical Domains:** Inflation, GDP, Monetary/Banking, Labor, FX/Gold/Housing, Trade, Budget, Capital Markets, Welfare.
* **50+ Indicators:** From daily market prices to annual welfare statistics.
* **9+ Data Sources:** Mix of international APIs (World Bank, IMF, EIA, OPEC) and domestic scraped sources (CBI, SCI, TSETMC, TGJU, HBSIR).
* **Historical Depth:** 50+ years where available, with chain-linked continuity.

---

## 3. Background

### 3.1 Key Research Findings

#### 1. Data Source Classification

| Difficulty | Sources                               | Approach                                       |
| ---------- | ------------------------------------- | ---------------------------------------------- |
| Easy       | World Bank, IMF DataMapper, EIA       | API-based; start here to validate architecture |
| Medium     | TSETMC via finpy-tse/TseClient, HBSIR | Unofficial APIs / Python packages              |
| Hard       | CBI TSD, SCI, TGJU                    | Production-grade web scraping                  |

#### 2. Time-Series Database Patterns

* Use the **TimescaleDB extension on PostgreSQL** for hypertables with automatic partitioning.

* Implement a wide-table design for indicators:

  `timestamp, indicator_id, value, metadata`

* Create separate **staging/bronze/silver/gold** layers following the Medallion architecture.

* Index on `(indicator_id, timestamp)` for fast time-series queries.

#### 3. Chain-Linking Algorithm

* Calculate growth rates during overlap periods between base years.
* Apply the splice method:

  * Use latest base-year values.
  * Extend backward using historical growth rates.
* Log all transformations with:

  * `original_value`
  * `linked_value`
  * `base_year_from`
  * `base_year_to`
  * `confidence_score`

#### 4. Web Scraping Architecture

* Use **Playwright** for JavaScript-heavy sites.
* Implement request throttling and exponential backoff with jitter.
* Rotate user agents using `fake-useragent`.
* Store raw HTML in the staging layer before parsing to allow re-parsing without re-scraping.

#### 5. Python Dashboard Framework

* **Streamlit** is recommended for economic dashboards because of its simplicity, fast iteration, and built-in caching.
* **Plotly** should be used for interactive time-series charts.
* Support CSV/Excel export for analysts.

---

# 4. Proposed Solution

Build a 4-layer data platform following the **Medallion architecture**.

```text
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                      │
│  Streamlit Dashboard (Plotly charts, filters, exports)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     GOLD LAYER (Analysis-Ready)             │
│  • Chain-linked time series with consistent base years      │
│  • Harmonized frequencies (daily/monthly/quarterly/annual)  │
│  • Calculated indicators (MoM/YoY inflation, real GDP, etc) │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     SILVER LAYER (Cleaned)                  │
│  • Parsed and validated data                                │
│  • Null handling, outlier detection                         │
│  • Metadata enrichment (source, collection_date, etc)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     BRONZE LAYER (Raw Ingestion)            │
│  • Raw API responses (JSON)                                 │
│  • Raw HTML from scraped pages                              │
│  • Downloaded Excel/PDF files                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     CONNECTOR LAYER                         │
│  • World Bank API connector                                 │
│  • IMF API connector                                        │
│  • EIA/OPEC connectors                                      │
│  • CBI/SCI/TGJU scrapers (Playwright-based)                 │
│  • TSETMC connector (finpy-tse wrapper)                     │
│  • HBSIR connector (Python package wrapper)                 │
└─────────────────────────────────────────────────────────────┘
```

### Infrastructure

* PostgreSQL 15 + TimescaleDB extension in Docker.
* Python 3.11+ environment with Poetry for dependency management.
* Airflow (lightweight local setup) for orchestration and scheduling.
* Docker Compose for all services.

---

# 5. Task Breakdown

## Recommended Data Source Priority

Start with **one API source (World Bank) + one scraping source (TGJU)** to validate the full architecture end-to-end before scaling to all 9+ sources.

This approach:

* Validates both easy (API) and hard (scraping) patterns early.
* World Bank provides long historical series for testing chain-linking.
* TGJU provides daily data for testing frequency harmonization.
* Minimizes rework if architecture needs adjustment.

---

# 6. Phase 1 — Foundation & Infrastructure

**Timeline:** Week 1–2

## Task 1: Project Scaffolding and Docker Environment

* Set up Python project structure with Poetry for dependency management.
* Create Docker Compose configuration for PostgreSQL 15 + TimescaleDB extension.
* Configure development environment with:

  * Ruff
  * Black
  * Mypy
* Set up pytest framework with fixtures for database testing.
* Create `.env` template for configuration management.

**Tests:**

* Verify Docker containers start correctly.
* Verify database connection succeeds.
* Verify pytest runs.

**Demo:**

* Run `docker-compose up`.
* Connect to PostgreSQL.
* Run `make test` successfully.

## Task 2: Database Schema Design with TimescaleDB

* Design 4-layer schema:

  * `bronze_raw`
  * `silver_cleaned`
  * `gold_analytical`
  * `metadata`
* Create hypertables for time-series data with automatic partitioning.
* Implement indicator catalog table:

  * `indicator_id`
  * `name`
  * `domain`
  * `unit`
  * `frequency`
  * `source`
* Create audit/lineage tables:

  * `data_collection_log`
  * `transformation_log`
  * `chain_linking_log`
* Write Alembic migrations for schema versioning.
* Add indexes optimized for time-series queries:

  * `(indicator_id, timestamp)`

**Tests:**

* Unit tests for schema creation.
* Constraint validation.
* Hypertable configuration.

**Demo:**

* Show database schema diagram.
* Query indicator catalog.
* Insert and query sample time-series data.

## Task 3: Base Connector Protocol and Testing Framework

* Define abstract base class `DataConnector` with standard interface:

  * `connect`
  * `discover`
  * `fetch`
  * `validate`
* Implement Bronze/Silver/Gold layer abstractions.
* Create connector testing utilities:

  * Mock responses.
  * Fixture data.
* Build data validation framework:

  * Schema validation.
  * Null checks.
  * Date range checks.
* Implement error handling hierarchy:

  * `ConnectionError`
  * `ParsingError`
  * `ValidationError`

**Tests:**

* Test connector protocol with mock implementation.
* Test validation framework.

**Demo:**

* Show base connector interface.
* Run validation tests with intentionally malformed data.

---

# 7. Phase 2 — API-Based Connector: World Bank

**Timeline:** Week 2–3

## Task 4: World Bank Connector Implementation

* Implement World Bank API v2 connector using `requests`.
* Handle:

  * Pagination.
  * Country filtering (`IRN`).
  * Indicator selection.
* Fetch 50+ years of annual macroeconomic indicators:

  * GDP
  * Trade
  * Population
  * Energy
* Implement Bronze-layer ingestion:

  * Raw JSON storage.
  * Metadata.
* Add request rate limiting and retry logic with exponential backoff.

**Tests:**

* Unit tests with mocked API responses.
* Optional integration tests with the live API.

**Demo:**

* Run connector.
* Show raw JSON in Bronze layer.
* Print summary statistics.

## Task 5: World Bank Data Transformation Pipeline

**Pipeline:** Bronze → Silver → Gold

* Parse Bronze JSON into structured Silver tables.
* Handle missing values and data quality issues.
* Implement Gold-layer transformations:

  * Calculate growth rates.
  * Format data for analysis.
* Add data lineage tracking:

  * Source.
  * Collection timestamp.
  * Transformation steps.
* Create reusable transformation utilities for other connectors.

**Tests:**

Test each layer transformation with:

* Nulls.
* Malformed dates.
* Duplicate records.
* Other edge cases.

**Demo:**

* Show the same indicator across all three layers.
* Query the Gold layer for analysis-ready GDP data.

## Task 6: Automated Chain-Linking for World Bank Data

* Detect base-year changes in historical series, e.g.:

  * GDP 2011 base.
  * GDP 2016 base.
* Implement splice method:

  * Calculate overlap growth rates.
  * Extend backward/forward.
* Log all chain-linking operations with confidence scores.
* Create validation reports comparing linked vs. original series.
* Add unit tests for the chain-linking algorithm using synthetic data.

**Tests:**

* Test chain-linking with known base-year transitions.
* Validate conservation of growth rates.

**Demo:**

* Show GDP series before/after chain-linking.
* Display audit log.
* Plot comparison chart.

---

# 8. Phase 3 — Production-Grade Web Scraper: TGJU

**Timeline:** Week 3–4

## Task 7: TGJU Scraper Foundation with Playwright

* Set up Playwright for headless browser automation.
* Implement user-agent rotation using `fake-useragent`.
* Build request throttling with exponential backoff and jitter.
* Create HTML storage in Bronze layer:

  * Raw responses.
  * Timestamp.
* Add comprehensive error handling and retry logic.
* Implement scraper health monitoring:

  * Success rate.
  * Response time tracking.

**Tests:**

* Test scraper with mock HTML responses.
* Test retry logic.
* Test user-agent rotation.

**Demo:**

* Scrape TGJU homepage.
* Show raw HTML in Bronze.
* Demonstrate retry behavior on timeout.

## Task 8: TGJU Parser for FX and Gold Prices

* Parse daily USD free-market exchange rate from TGJU.
* Extract gold coin prices:

  * Emami.
  * 18K gold.
  * Coin premium.
* Handle Persian/Farsi number formatting and date conversion.
* Implement Silver-layer validation:

  * Price reasonableness checks.
  * Outlier detection.
* Create Gold layer with calculated fields:

  * Daily returns.
  * 30-day moving averages.

**Tests:**

* Test parser with sample HTML fixtures.
* Test Persian number conversion.
* Test outlier detection.

**Demo:**

* Show parsed daily FX/gold prices in Silver layer.
* Query Gold layer for recent trends.

## Task 9: Scraper Orchestration and Scheduling

* Set up Apache Airflow in Docker using `LocalExecutor` for local development.
* Create DAG for daily TGJU scraping:

  * Run at 11 PM Iran time.
* Implement failure alerting:

  * Log errors.
  * Send notifications on repeated failures.
* Add backfill capability for historical data collection.
* Create monitoring dashboard using Airflow UI.

**Tests:**

* Test DAG execution manually.
* Test backfill logic.
* Test failure recovery.

**Demo:**

* Show Airflow UI.
* Manually trigger TGJU DAG.
* Show successful Bronze → Gold data flow.

---

# 9. Phase 4 — Additional API Connectors

**Timeline:** Week 4–5

## Task 10: IMF DataMapper Connector

* Implement IMF API connector for Iran macroeconomic indicators.
* Fetch:

  * Inflation.
  * GDP growth.
  * 5-year forecasts.
* Handle SDMX 2.1 data format and JSON responses.
* Integrate into Bronze → Silver → Gold pipeline.

**Tests:**

* Unit tests with mocked IMF responses.
* Validation tests.

**Demo:**

* Query IMF forecasts for Iran.
* Compare with World Bank historical data.

## Task 11: EIA and OPEC Energy Data Connectors

* Implement EIA API connector for Iran crude oil production estimates.
* Parse OPEC XML/CSV for:

  * Basket prices.
  * Iran export data.
* Handle monthly frequency.
* Transform to analysis-ready format.
* Add to Gold layer with proper metadata tagging.

**Tests:**

* Test both connectors with sample responses.
* Test frequency conversion.

**Demo:**

* Show Iran oil production time series.
* Plot OPEC basket prices.

---

# 10. Phase 5 — Domestic Scrapers: CBI & SCI

**Timeline:** Week 5–6

## Task 12: CBI TSD Scraper for Monetary Aggregates

* Scrape CBI TSD system for:

  * Monetary base (M0).
  * Liquidity (M2).
* Handle Excel file downloads and parsing using:

  * `pandas`
  * `openpyxl`
* Extract Tehran housing market price index.
* Implement quarterly and monthly frequency handling.

**Tests:**

* Test Excel parsing with fixture files.
* Test date extraction from Persian calendar.

**Demo:**

* Show M0/M2 time series in Gold layer.
* Plot monetary expansion trends.

## Task 13: SCI Scraper for CPI and Unemployment

* Scrape Statistical Center of Iran for CPI data:

  * Headline CPI.
  * Decile-level CPI.
* Extract quarterly unemployment statistics.
* Handle PDF parsing using `pdfplumber` when necessary.
* Implement CPI chain-linking across multiple base years:

  * 2011
  * 2016
  * 2021

**Tests:**

* Test PDF parsing.
* Test CPI chain-linking across three base-year transitions.

**Demo:**

* Show continuous 20-year CPI series after chain-linking.
* Plot inflation by income decile.

---

# 11. Phase 6 — Stock Market & Survey Data

**Timeline:** Week 6–7

## Task 14: TSETMC Connector Using `finpy-tse`

* Integrate `finpy-tse` or `TseClient` for Tehran Stock Exchange data.
* Fetch:

  * TEDPIX index.
  * Trading value.
  * P/E ratio.
* Handle market holidays and missing data.
* Implement downsampling to monthly frequency for cross-domain analysis.

**Tests:**

* Test with mock market data.
* Test downsampling logic.

**Demo:**

* Show daily TEDPIX in Gold layer.
* Plot alongside monthly CPI/FX for correlation analysis.

## Task 15: HBSIR Connector for Household Survey Data

* Integrate `hbsir` Python package for Iran Open Data.
* Extract:

  * Gini coefficient.
  * Poverty rates.
  * Income decile data.
* Transform into Gold layer with proper temporal alignment.

**Tests:**

* Test HBSIR package integration.
* Validate data transformations.

**Demo:**

* Show income inequality trends over 10+ years.
* Export to CSV.

---

# 12. Phase 7 — Dashboard Development

**Timeline:** Week 7–8

## Task 16: Streamlit Dashboard Foundation

* Set up Streamlit application structure with multi-page layout.
* Implement database connection pooling for efficient queries.
* Create shared components:

  * Date range picker.
  * Indicator selector.
  * Download button.
* Add session-state management and caching for performance.
* Style dashboard with custom CSS matching an economic-analysis aesthetic.

**Tests:**

* Test Streamlit pages load.
* Test database queries with various filters.

**Demo:**

* Launch dashboard.
* Navigate between pages.
* Show caching behavior.

## Task 17: Time-Series Visualization Pages

* Build interactive Plotly charts for:

  * Single-indicator analysis.
  * Multi-indicator comparisons.
* Implement domain-specific pages:

  * Inflation.
  * Monetary.
  * FX/Gold.
  * Etc.
* Add MoM/YoY/Annual toggle.
* Create chart export functionality:

  * PNG.
  * SVG.
  * Interactive HTML.
* Implement cross-domain correlation heatmaps.

**Tests:**

* Test chart rendering with various date ranges.
* Test export functionality.

**Demo:**

* Show inflation dashboard with CPI across deciles.
* Export chart and data.

## Task 18: Data Export and Advanced Features

* Implement CSV/Excel export with user-selected indicators and date ranges.
* Add data quality indicators:

  * Chain-linked vs. original.
  * Missing-data flags.
* Create data catalog page showing all available indicators with metadata.
* Implement basic search and filtering for indicators.
* Add "last updated" timestamps for each source.

**Tests:**

* Test export with various selections.
* Test search functionality.

**Demo:**

* Search for GDP indicators.
* Export 50-year dataset.
* Show data quality flags.

---

# 13. Phase 8 — Documentation & Production Readiness

**Timeline:** Week 8

## Task 19: Comprehensive Documentation

* Write README with quickstart guide:

  * Docker setup.
  * Running dashboard.
* Document each connector's implementation details and limitations.
* Create data dictionary for all 50+ indicators with sources and definitions.
* Write troubleshooting guide covering:

  * Scraper failures.
  * Database connection issues.
* Add architecture diagrams and data-flow documentation.

**Tests:**

* Follow README on a fresh machine or VM.
* Verify all documented steps work.

**Demo:**

* Walk through documentation.
* Show architecture diagram.

## Task 20: Testing, Monitoring, and CI/CD

* Achieve 80%+ code coverage with unit and integration tests.
* Set up GitHub Actions for automated testing on commit.
* Create monitoring scripts for:

  * Scraper health.
  * Data freshness.
* Implement database backup and restore procedures.
* Add performance benchmarks for key queries.
* Write operational runbook for daily maintenance.

**Tests:**

* Run full test suite.
* Verify CI/CD pipeline.
* Test backup/restore.

**Demo:**

* Show CI/CD passing.
* Demonstrate backup/restore.
* Show monitoring dashboard.

---

# 14. Success Criteria

## 14.1 Functional Acceptance Criteria

* [ ] All 9+ data sources successfully connected and ingesting data.
* [ ] 50+ economic indicators available in Gold layer with proper metadata.
* [ ] Chain-linking automatically applied to all base-year transitions with <5% error in overlap periods.
* [ ] Daily scraping successfully running for TGJU and TSETMC sources.
* [ ] Streamlit dashboard loads in <3 seconds.
* [ ] Queries return in <1 second.
* [ ] Users can export any indicator combination as CSV/Excel.
* [ ] All 9 analytical domains represented with at least 3 indicators each.

## 14.2 Data Quality Criteria

* [ ] <2% missing values in Gold layer for indicators with regular publication schedules.
* [ ] 100% of scraped data passes validation rules, including date formats and numeric ranges.
* [ ] Chain-linked series preserve growth rates within ±1% of the original during overlap periods.
* [ ] All data transformations logged in audit tables for reproducibility.

## 14.3 Technical Criteria

* [ ] 80%+ code coverage with passing tests.
* [ ] Docker Compose setup completes in <5 minutes on a fresh machine.
* [ ] Zero manual SQL queries required for normal operation.
* [ ] Scrapers successfully handle rate limiting and temporary failures with retry logic.
* [ ] PostgreSQL queries are optimized with proper indexes and query plans show index usage.

## 14.4 Production-Readiness Criteria

* [ ] Comprehensive documentation allows a new developer to run the system in <1 hour.
* [ ] Monitoring dashboard shows health status of all connectors.
* [ ] Database backup/restore procedures documented and tested.
* [ ] Troubleshooting guide covers 10+ common failure scenarios.

---

# 15. Risks, Assumptions & Unknowns

## 15.1 Major Risks

### 1. Website Structure Changes — High Risk

**Risk:** CBI, SCI, and TGJU may change HTML structure without notice, breaking scrapers.

**Mitigation:**

* Store raw HTML in Bronze layer to allow re-parsing.
* Implement scraper health alerts.
* Create versioned parsers for different site layouts.

### 2. Data Quality Inconsistencies — Medium Risk

**Risk:** Domestic sources may have gaps, retroactive revisions, or inconsistent base years.

**Mitigation:**

* Implement comprehensive validation.
* Log all anomalies.
* Provide data-quality flags in the dashboard.
* Create a manual review queue for outliers.

### 3. Scraper Detection and Blocking — Medium Risk

**Risk:** Production-grade scraping may still trigger anti-bot measures.

**Mitigation:**

* User-agent rotation.
* Request throttling.
* Monitor for CAPTCHA/blocks.
* Provide fallback to manual download with clear error messages.

### 4. Performance with Large Historical Dataset — Low Risk

**Risk:** 50 years × 50 indicators × daily frequency may produce millions of rows and cause slow queries.

**Mitigation:**

* TimescaleDB hypertables with automatic partitioning.
* Proper indexing.
* Dashboard query optimization.
* Caching.

### 5. Docker Resource Constraints — Low Risk

**Risk:** PostgreSQL + Airflow + Playwright may exceed local machine resources.

**Mitigation:**

* Document minimum requirements.
* Recommend 16 GB RAM.
* Provide a lightweight configuration option that disables Airflow and uses cron.

---

## 15.2 Key Assumptions

* User has Docker and Docker Compose installed or is willing to install them.
* Local machine has sufficient resources:

  * 16 GB RAM.
  * 50 GB disk for historical data.
* Internet connection is stable for daily scraping operations.
* Domestic Iranian websites remain accessible without additional blocking/censorship.
* IMF/World Bank APIs remain free and accessible without authentication.
* User is comfortable running Python scripts and Docker commands.

---

## 15.3 Unknowns / Validation Needed

| Unknown                                                                           | Validation                                 |
| --------------------------------------------------------------------------------- | ------------------------------------------ |
| Do all CPI/GDP revisions have sufficient overlap for reliable chain-linking?      | Validate during Tasks 6 and 13             |
| Can TGJU be reliably scraped daily without blocks?                                | Validate during Tasks 7–8                  |
| Is the HBSIR package actively maintained?                                         | Validate during Task 15                    |
| Is Airflow too heavy for local setup?                                             | Consider APScheduler or cron during Task 9 |
| Does TimescaleDB provide meaningful benefits over plain PostgreSQL at this scale? | Benchmark during Task 2                    |

---

# 16. Implementation Phases Summary

## Phase 1 — Foundation

**Timeline:** Week 1–2

**Goal:** Set up development environment and database architecture.

**Deliverables:**

* [ ] Docker Compose environment running PostgreSQL + TimescaleDB.
* [ ] Database schema with 4-layer architecture and hypertables.
* [ ] Base connector protocol and testing framework.

**Validation:** Can create a test connector, insert time-series data, and query efficiently.

---

## Phase 2 — API Connector MVP

**Timeline:** Week 2–3

**Goal:** Validate the full pipeline with World Bank data.

**Deliverables:**

* [ ] World Bank connector with Bronze/Silver/Gold transformations.
* [ ] Automated chain-linking algorithm.
* [ ] 50+ years of Iran macroeconomic data in Gold layer.

**Validation:** Can query analysis-ready GDP data with a continuous chain-linked series.

---

## Phase 3 — Web Scraper MVP

**Timeline:** Week 3–4

**Goal:** Validate production-grade scraping with TGJU.

**Deliverables:**

* [ ] Playwright-based scraper with anti-detection features.
* [ ] TGJU parser for daily FX and gold prices.
* [ ] Airflow orchestration for scheduled scraping.

**Validation:** Daily TGJU scraping runs automatically and data flows to the Gold layer.

---

## Phase 4 — Additional APIs

**Timeline:** Week 4–5

**Goal:** Expand data coverage with IMF and energy sources.

**Deliverables:**

* [ ] IMF DataMapper connector with forecasts.
* [ ] EIA and OPEC energy data connectors.

**Validation:** Can compare World Bank historical data with IMF forecasts and plot oil production trends.

---

## Phase 5 — Complex Domestic Scrapers

**Timeline:** Week 5–6

**Goal:** Tackle the most challenging data sources.

**Deliverables:**

* [ ] CBI TSD scraper for monetary aggregates.
* [ ] SCI scraper for CPI and unemployment with multi-base-year chain-linking.

**Validation:** Continuous 20-year CPI series with three base-year transitions handled automatically.

---

## Phase 6 — Market & Survey Data

**Timeline:** Week 6–7

**Goal:** Complete data source coverage.

**Deliverables:**

* [ ] TSETMC connector for stock market data.
* [ ] HBSIR connector for household survey data.

**Validation:** All 9 analytical domains have data available.

---

## Phase 7 — Dashboard

**Timeline:** Week 7–8

**Goal:** Build user-facing analytical interface.

**Deliverables:**

* [ ] Multi-page Streamlit dashboard with interactive charts.
* [ ] Domain-specific visualization pages.
* [ ] CSV/Excel export functionality.

**Validation:** Analyst can explore data, create publication-ready charts, and export datasets.

---

## Phase 8 — Production Readiness

**Timeline:** Week 8

**Goal:** Ensure maintainability and reliability.

**Deliverables:**

* [ ] Comprehensive documentation and runbooks.
* [ ] 80%+ test coverage with CI/CD.
* [ ] Monitoring and backup procedures.

**Validation:** A new developer can set up and run the system by following the documentation.

---

# 17. Future Considerations — Post-MVP

## 17.1 Post-MVP Improvements

* Advanced forecasting models:

  * ARIMA.
  * Prophet.
  * ML-based models.
* Real-time dashboard updates using WebSocket connections.
* User authentication and multi-user support.
* Custom alert system:

  * Email.
  * Telegram.
* Advanced data-quality monitoring with anomaly detection.
* API layer to expose cleaned data to external tools:

  * R.
  * Jupyter notebooks.

## 17.2 Additional Data Sources

* Tehran municipality data:

  * Traffic.
  * Pollution.
* Iran Commodity Exchange (IME) for commodity prices.
* Ministry of Energy for electricity/water consumption.
* Iran National Tax Administration for revenue statistics.
* Additional provincial data from SCI.

## 17.3 Advanced Features

* Scenario analysis tools and what-if modeling.
* Automated report generation:

  * Weekly economic briefs.
  * Monthly economic briefs.
* Integration with international sanctions timeline.
* Cross-country comparison dashboards.
* Mobile-responsive dashboard version.

## 17.4 Scaling Opportunities

* Cloud deployment option on AWS/GCP with Terraform.
* Distributed scraping with proxy rotation services.
* Data versioning with DVC or similar tools.
* Production-grade orchestration using Prefect/Dagster as alternatives to Airflow.
* Separate read replicas for dashboard queries.

---

# 18. Appendix

## 18.1 Technology Stack Summary

| Category              | Technology                          |
| --------------------- | ----------------------------------- |
| Language              | Python 3.11+                        |
| Database              | PostgreSQL 15 + TimescaleDB         |
| Orchestration         | Apache Airflow (LocalExecutor)      |
| Web Scraping          | Playwright, BeautifulSoup, requests |
| Dashboard             | Streamlit + Plotly                  |
| Testing               | pytest + pytest-cov                 |
| Dependency Management | Poetry                              |
| Containerization      | Docker + Docker Compose             |
| CI/CD                 | GitHub Actions (optional)           |

---

## 18.2 Proposed Repository Structure

```text
iran-macro-platform/
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── src/
│   ├── connectors/          # All data source connectors
│   │   ├── base.py          # Abstract base connector
│   │   ├── world_bank.py
│   │   ├── imf.py
│   │   ├── tgju_scraper.py
│   │   └── ...
│   ├── etl/                 # Bronze/Silver/Gold transformations
│   ├── chain_linking/       # Base-year adjustment algorithms
│   ├── database/            # Schema, migrations, queries
│   └── utils/               # Validation, logging, config
├── dashboard/
│   ├── app.py               # Streamlit entry point
│   ├── pages/               # Multi-page dashboard
│   └── components/          # Reusable UI components
├── airflow/
│   ├── dags/                # DAG definitions
│   └── config/              # Airflow configuration
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/            # Test data
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── runbooks/
└── scripts/                 # Utility scripts (backup, monitoring)
```

---

## 18.3 Glossary

| Term              | Definition                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Bronze Layer**  | Raw ingested data (JSON, HTML, Excel) with minimal processing.                               |
| **Silver Layer**  | Cleaned and validated data with standardized schema.                                         |
| **Gold Layer**    | Analysis-ready data with transformations, chain-linking, and calculated fields.              |
| **Chain-linking** | Method to create continuous time series across base-year changes by preserving growth rates. |
| **Hypertable**    | TimescaleDB's automatic partitioning mechanism for time-series data.                         |
| **MoM/YoY**       | Month-over-Month / Year-over-Year growth rates.                                              |
