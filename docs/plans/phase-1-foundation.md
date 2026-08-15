# Task: Phase 1 — Foundation & Infrastructure Setup

## Task Description

Set up the foundational development environment and infrastructure for the Iran Macroeconomic Data Platform. This includes project scaffolding with Poetry, Docker Compose environment with PostgreSQL + TimescaleDB, database schema design following the medallion architecture, and the base connector protocol framework.

**Why:** Establishes the technical foundation required for all subsequent phases. Without this infrastructure, data connectors, ETL pipelines, and the dashboard cannot be built.

**Timeline:** Week 1-2

## Scope

### In Scope
- [ ] Python project structure with Poetry dependency management
- [ ] Docker Compose configuration for PostgreSQL 15 + TimescaleDB
- [ ] Development tooling: ruff, mypy, pytest
- [ ] 4-layer database schema (Bronze/Silver/Gold/Metadata)
- [ ] TimescaleDB hypertables for time-series optimization
- [ ] Alembic migrations framework
- [ ] Abstract DataConnector protocol (base class)
- [ ] Testing framework with fixtures
- [ ] Configuration management (.env template)
- [ ] Basic Makefile for common commands

### Out of Scope
- [ ] Actual data source connectors (Phase 2+)
- [ ] ETL transformation logic (Phase 2+)
- [ ] Chain-linking algorithm implementation (Phase 2)
- [ ] Airflow orchestration (Phase 3)
- [ ] Dashboard implementation (Phase 7)
- [ ] CI/CD pipeline (Phase 8)

## Context

**Current State:** Project contains only planning documents (PRD.md, AGENTS.md, research docs). No code or infrastructure exists.

**Architecture Pattern:** Medallion architecture with 4 layers:
- **Bronze:** Raw data storage (JSON, HTML, Excel)
- **Silver:** Cleaned and validated data
- **Gold:** Analysis-ready with chain-linking and calculations
- **Metadata:** Indicator catalog, lineage, quality metrics

**Deployment Constraint:** Must run locally on analyst's laptop via Docker Compose (no cloud infrastructure).

## Proposed Approach

Follow the PRD's Phase 1 task breakdown:

1. **Task 1:** Scaffolding and Docker environment
2. **Task 2:** Database schema with TimescaleDB
3. **Task 3:** Base connector protocol and testing framework

Use industry-standard Python tooling and follow project conventions documented in AGENTS.md.

## Task Metadata

**Type:** Foundation / New Capability  
**Complexity:** Medium  
**Affected Areas:** Infrastructure, Database, Core Framework  
**Dependencies:** None (starting from scratch)

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

**None** - This is the initial implementation. Reference documents:
- `PRD.md` - Sections 6-7 (Phase 1 tasks)
- `AGENTS.md` - Tech stack, naming conventions, architecture rules
- `docs/research/init-research.md` - Data source requirements

### Patterns to Follow

**Naming Conventions (from AGENTS.md):**
- Files/modules: snake_case (`world_bank.py`)
- Classes: PascalCase (`DataConnector`)
- Functions/variables: snake_case (`fetch_indicators`)
- Constants: UPPER_SNAKE_CASE (`MAX_RETRIES`)

**Structure:**
- Separation of concerns: one connector per file
- Type hints required for all public functions
- Custom exception hierarchy
- Structured logging with context

**Testing:**
- pytest with fixtures in `tests/fixtures/`
- 80%+ coverage target
- Mock external dependencies in unit tests
- Integration tests marked with `@pytest.mark.integration`

---

## IMPLEMENTATION PLAN

### Phase 1: Project Scaffolding
- Initialize Poetry project
- Configure pyproject.toml with dependencies
- Set up directory structure
- Create Makefile for common commands
- Add .env.template for configuration

### Phase 2: Docker Infrastructure
- Create docker-compose.yml with PostgreSQL + TimescaleDB
- Configure database initialization scripts
- Test database connectivity

### Phase 3: Database Schema
- Design 4-layer schema (Bronze/Silver/Gold/Metadata)
- Create SQLAlchemy models
- Configure TimescaleDB hypertables
- Set up Alembic migrations
- Add indexes for time-series queries

### Phase 4: Connector Framework
- Define DataConnector abstract base class
- Create custom exception hierarchy
- Build validation framework
- Add testing utilities

### Phase 5: Development Tooling
- Configure ruff for linting/formatting
- Set up mypy for type checking
- Configure pytest with coverage
- Test all quality gates

---

## STEP-BY-STEP TASKS

### Task 1.1: CREATE project structure

- **IMPLEMENT:** Initialize Poetry project with Python 3.11+
- **PATTERN:** Standard Python project layout
- **DEPENDENCIES:** Poetry installed on system
- **VALIDATE:** `poetry --version && poetry install`

**Directory structure:**
```
iran-macro-platform/
├── src/
│   ├── __init__.py
│   ├── connectors/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   └── connection.py
│   ├── etl/
│   │   └── __init__.py
│   ├── chain_linking/
│   │   └── __init__.py
│   └── utils/
│       ├── __init__.py
│       ├── validation.py
│       ├── logging.py
│       └── config.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── __init__.py
│   ├── integration/
│   │   └── __init__.py
│   └── fixtures/
│       └── __init__.py
├── dashboard/
│   └── __init__.py
├── airflow/
│   └── dags/
├── scripts/
├── .env.template
├── pyproject.toml
├── Makefile
└── README.md
```

### Task 1.2: CREATE pyproject.toml

- **IMPLEMENT:** Configure Poetry with core dependencies
- **DEPENDENCIES:**
  - sqlalchemy >= 2.0
  - psycopg2-binary
  - alembic
  - pydantic >= 2.0
  - python-dotenv
  - requests
  - pandas
  - pytest
  - pytest-cov
  - ruff
  - mypy
- **VALIDATE:** `poetry lock && poetry install`

### Task 1.3: CREATE docker-compose.yml

- **IMPLEMENT:** PostgreSQL 15 with TimescaleDB extension
- **GOTCHA:** Use timescale/timescaledb:latest-pg15 image
- **VALIDATE:** `docker-compose up -d && docker-compose ps`

**Configuration:**
- Port: 5432
- Database: iran_macro_db
- Volume for persistence
- Health checks

### Task 1.4: CREATE Makefile

- **IMPLEMENT:** Common commands for development workflow
- **COMMANDS:**
  - `make format`: Run ruff format
  - `make lint`: Run ruff check
  - `make typecheck`: Run mypy
  - `make test`: Run pytest with coverage
  - `make check`: Run all quality gates
  - `make db-up`: Start Docker services
  - `make db-down`: Stop Docker services
- **VALIDATE:** `make check`

### Task 1.5: CREATE .env.template

- **IMPLEMENT:** Template for environment variables
- **VARIABLES:**
  - DATABASE_URL
  - DATABASE_HOST
  - DATABASE_PORT
  - DATABASE_NAME
  - DATABASE_USER
  - DATABASE_PASSWORD
  - LOG_LEVEL
- **VALIDATE:** Copy to .env and test loading

### Task 2.1: CREATE database schema models

- **IMPLEMENT:** SQLAlchemy models for 4 layers
- **FILE:** `src/database/schema.py`
- **TABLES:**
  - `bronze_raw`: Raw data storage
  - `silver_cleaned`: Cleaned data
  - `gold_analytical`: Analysis-ready data
  - `indicator_catalog`: Indicator metadata
  - `data_collection_log`: Collection audit
  - `transformation_log`: Transform audit
  - `chain_linking_log`: Chain-linking audit
- **VALIDATE:** Python syntax and imports

### Task 2.2: CREATE TimescaleDB hypertable setup

- **IMPLEMENT:** Hypertable configuration for time-series tables
- **PATTERN:** Use `create_hypertable()` after table creation
- **INDEX:** (indicator_id, timestamp) for fast queries
- **VALIDATE:** SQL generation from models

### Task 2.3: CREATE Alembic configuration

- **IMPLEMENT:** Initialize Alembic for migrations
- **COMMANDS:**
  - `alembic init alembic`
  - Configure alembic.ini with database URL
  - Create initial migration
- **VALIDATE:** `alembic upgrade head`

### Task 2.4: CREATE database connection utility

- **IMPLEMENT:** Connection pooling and session management
- **FILE:** `src/database/connection.py`
- **PATTERN:** SQLAlchemy engine and session factory
- **VALIDATE:** Test connection with query

### Task 3.1: CREATE DataConnector abstract base class

- **IMPLEMENT:** Define connector protocol
- **FILE:** `src/connectors/base.py`
- **METHODS:**
  - `connect() -> bool`
  - `discover() -> List[IndicatorMetadata]`
  - `fetch(indicator_id, start_date, end_date) -> pd.DataFrame`
  - `validate(data: pd.DataFrame) -> ValidationResult`
- **PATTERN:** Use ABC and abstractmethod decorators
- **VALIDATE:** Import and instantiation attempt (should fail for abstract class)

### Task 3.2: CREATE custom exception hierarchy

- **IMPLEMENT:** Exception classes for error handling
- **FILE:** `src/utils/exceptions.py`
- **CLASSES:**
  - `DataPlatformError` (base)
  - `ConnectionError`
  - `DataRetrievalError`
  - `ValidationError`
  - `ParsingError`
- **VALIDATE:** Import and raise tests

### Task 3.3: CREATE validation framework

- **IMPLEMENT:** Data validation utilities
- **FILE:** `src/utils/validation.py`
- **FUNCTIONS:**
  - Schema validation
  - Date range validation
  - Null percentage check
  - Outlier detection (IQR method)
- **VALIDATE:** Unit tests with sample data

### Task 3.4: CREATE logging configuration

- **IMPLEMENT:** Structured logging setup
- **FILE:** `src/utils/logging.py`
- **PATTERN:** JSON formatting for Airflow compatibility
- **VALIDATE:** Log message creation and formatting

### Task 3.5: CREATE configuration management

- **IMPLEMENT:** Pydantic config classes
- **FILE:** `src/utils/config.py`
- **PATTERN:** Load from .env with validation
- **VALIDATE:** Config instantiation test

### Task 4.1: CREATE pytest configuration

- **IMPLEMENT:** pytest.ini and conftest.py
- **MARKERS:**
  - `integration`: Integration tests (skipped by default)
  - `live`: Live API tests (skipped by default)
- **COVERAGE:** Minimum 80% threshold
- **VALIDATE:** `pytest --collect-only`

### Task 4.2: CREATE test fixtures

- **IMPLEMENT:** Database fixtures and mock data
- **FILE:** `tests/conftest.py`
- **FIXTURES:**
  - `db_session`: Test database session
  - `sample_indicator`: Mock indicator metadata
  - `sample_timeseries`: Mock time-series data
- **VALIDATE:** Fixture discovery

### Task 4.3: CREATE base connector tests

- **IMPLEMENT:** Test DataConnector protocol
- **FILE:** `tests/unit/connectors/test_base.py`
- **TESTS:**
  - Abstract class cannot be instantiated
  - Protocol methods are defined
- **VALIDATE:** `make test`

### Task 5.1: CONFIGURE ruff

- **IMPLEMENT:** Add ruff configuration to pyproject.toml
- **SETTINGS:**
  - Line length: 100
  - Target Python 3.11+
  - Select: E, F, I, N, W
- **VALIDATE:** `make format && make lint`

### Task 5.2: CONFIGURE mypy

- **IMPLEMENT:** Add mypy configuration to pyproject.toml
- **SETTINGS:**
  - Strict mode
  - Ignore missing imports for third-party libs
- **VALIDATE:** `make typecheck`

### Task 5.3: CREATE README.md

- **IMPLEMENT:** Quickstart documentation
- **SECTIONS:**
  - Project overview
  - Prerequisites
  - Setup instructions
  - Running tests
  - Development workflow
- **VALIDATE:** Follow instructions on fresh environment

---

## TESTING & VALIDATION

### Unit Tests

```python
# tests/unit/database/test_schema.py
- Test SQLAlchemy model creation
- Test table relationships

# tests/unit/connectors/test_base.py
- Test DataConnector protocol
- Test abstract methods

# tests/unit/utils/test_validation.py
- Test schema validation
- Test outlier detection
- Test null checks
```

### Integration Tests

```python
# tests/integration/test_database.py
- Test database connection
- Test table creation
- Test hypertable setup
- Test data insertion and querying

# Mark with @pytest.mark.integration
```

### Edge Cases

- Database connection failures
- Missing environment variables
- Invalid configuration values
- SQLAlchemy model validation errors

---

## VALIDATION COMMANDS

### Level 1: Environment Setup

```bash
poetry --version
docker --version
docker-compose --version
```

### Level 2: Docker Services

```bash
make db-up
docker-compose ps
# Should show postgres container running and healthy
```

### Level 3: Database Connection

```bash
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "\dt"
# Should list tables after migration
```

### Level 4: Code Quality

```bash
make format    # Should format without errors
make lint      # Should pass all checks
make typecheck # Should pass type checking
```

### Level 5: Tests

```bash
make test      # Should pass all unit tests with 80%+ coverage
pytest tests/integration/ --markers integration  # Should pass integration tests
```

### Level 6: Full Validation

```bash
make check     # Should pass all quality gates
alembic current # Should show current migration
alembic upgrade head # Should apply migrations successfully
```

### Level 7: Manual Validation

1. Start Docker services: `make db-up`
2. Run migrations: `alembic upgrade head`
3. Connect to database: `docker-compose exec postgres psql -U iran_macro -d iran_macro_db`
4. Verify tables exist: `\dt`
5. Verify TimescaleDB extension: `SELECT * FROM timescaledb_information.hypertables;`
6. Run test suite: `make test`
7. Check code quality: `make check`

---

## ACCEPTANCE CRITERIA

* [ ] Poetry project initialized with all dependencies installed
* [ ] Docker Compose successfully starts PostgreSQL + TimescaleDB
* [ ] Database connection works from Python code
* [ ] All 4 layers (Bronze/Silver/Gold/Metadata) have schema models
* [ ] TimescaleDB hypertables created for time-series tables
* [ ] Alembic migrations framework configured and working
* [ ] DataConnector abstract base class defined with protocol methods
* [ ] Custom exception hierarchy implemented
* [ ] Validation framework with schema/date/outlier checks
* [ ] Logging configuration with JSON formatting
* [ ] Configuration management with Pydantic
* [ ] pytest framework with fixtures and markers
* [ ] ruff, mypy, pytest all configured and passing
* [ ] Makefile provides all common commands
* [ ] README.md documents setup and usage
* [ ] All unit tests pass with 80%+ coverage
* [ ] Integration tests pass when run manually
* [ ] `make check` passes all quality gates

---

## RISKS & TRADE-OFFS

**Risk:** TimescaleDB complexity may be overkill for initial dataset size
- **Mitigation:** Validate during Task 2.2; can use plain PostgreSQL if needed
- **Trade-off:** Extra setup time vs. future performance benefits

**Risk:** Docker resource constraints on developer laptops
- **Mitigation:** Document minimum requirements (16GB RAM); provide lightweight config
- **Trade-off:** Convenience vs. resource usage

**Risk:** Poetry vs. pip/requirements.txt learning curve
- **Mitigation:** Document Poetry commands in README; provide quick reference
- **Trade-off:** Better dependency management vs. familiarity

**Assumption:** Developer has Docker and Python 3.11+ installed
- **Validation:** Document prerequisites clearly in README

**Assumption:** PostgreSQL 15 + TimescaleDB is stable and compatible
- **Validation:** Use official timescale/timescaledb Docker image

---

## NOTES

### Important Implementation Details

1. **Database Schema Design:**
   - Use JSONB columns for flexible metadata storage in Bronze layer
   - Add `created_at` and `updated_at` timestamps to all tables
   - Use UUIDs for primary keys where appropriate

2. **TimescaleDB Configuration:**
   - Partition hypertables by time (monthly chunks for daily data)
   - Create appropriate indexes after hypertable creation
   - Use compression policies for older data (Phase 8)

3. **Connector Protocol:**
   - Keep it minimal and flexible
   - Add methods as needed during Phase 2 implementation
   - Use Protocol/ABC hybrid for runtime checks

4. **Testing Strategy:**
   - Start with unit tests for all utilities
   - Add integration tests for database operations
   - Mock external dependencies (no live API calls in unit tests)

5. **Configuration:**
   - Use Pydantic for validation and type safety
   - Support both .env file and environment variables
   - Provide sensible defaults for development

### Deferred Decisions

- **Airflow vs. APScheduler:** Defer to Phase 3 based on resource usage
- **Compression policies:** Defer to Phase 8 (production readiness)
- **Connection pooling tuning:** Start with defaults, optimize later
- **Query optimization:** Defer to Phase 7 (dashboard implementation)

### Success Metrics

After Phase 1 completion:
- [ ] New developer can run `make db-up && make test` successfully in <10 minutes
- [ ] Can insert and query sample time-series data
- [ ] All quality gates pass
- [ ] Ready to implement first connector (World Bank - Phase 2)

---

## Confidence Assessment

**Confidence: 9/10**

**High confidence because:**
- Clear requirements in PRD and AGENTS.md
- Standard Python/PostgreSQL/Docker stack
- Well-defined scope with no external dependencies
- Starting from scratch (no legacy code to navigate)

**Slight uncertainty:**
- TimescaleDB behavior at this scale (validate during implementation)
- Optimal schema design may need iteration after Phase 2 feedback
- Exact SQLAlchemy patterns for hypertables need validation

**Recommendation:** Proceed with implementation. Adjust schema design after World Bank connector (Phase 2, Task 4) if needed.
