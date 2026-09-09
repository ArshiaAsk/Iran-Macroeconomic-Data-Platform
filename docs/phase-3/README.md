# Phase 3: TGJU Web Scraper Documentation

**Status:** ✅ Implementation Complete (Airflow Orchestration Pending)  
**Completion Date:** September 8, 2026

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Technical implementation details, architecture decisions, components | Developers |
| **[VALIDATION.md](VALIDATION.md)** | Step-by-step validation checklist with SQL queries | QA, Maintainers |

---

## What Was Built

### Components
- ✅ **TGJU Parser** (`src/connectors/tgju_parser.py`) - Persian number handling, HTML extraction
- ✅ **TGJU Scraper** (`src/connectors/tgju_scraper.py`) - Playwright browser automation
- ✅ **Integration Tests** (`tests/integration/test_tgju_pipeline.py`) - End-to-end pipeline validation
- ✅ **Unit Tests** - 84 tests (45 parser + 39 scraper)

### Coverage
- **Total Tests:** 100 (84 unit + 16 integration)
- **Passing:** 99 (15 integration + 84 unit)
- **Skipped:** 1 (live test, requires network)
- **Coverage:** 83.06% (exceeds 80% gate ✅)

### Indicators
1. `price_dollar_rl` - US Dollar (Free Market) in IRR
2. `geram18` - 18-Karat Gold in IRR/gram
3. `sekee` - Emami Gold Coin in IRR/coin

---

## Quick Start

### Prerequisites
```bash
# Install dependencies
poetry install
poetry run playwright install chromium

# Start database
make db-up

# Apply migrations
poetry run alembic upgrade head
```

### Run Tests
```bash
# All tests
make test-all

# Just TGJU integration tests
poetry run pytest tests/integration/test_tgju_pipeline.py -v
# Expected: 15 passed, 1 skipped
```

### Validate Implementation
Follow the step-by-step checklist in [VALIDATION.md](VALIDATION.md).

---

## Key Features

### 1. Persian/Farsi Data Handling
- **Persian digits:** `۱۲۳۴۵۶۷۸۹` → `0123456789`
- **Jalali calendar:** Persian dates converted to Gregorian
- **Number formatting:** Handles commas and Persian separators

### 2. Single-Observation Architecture
- TGJU shows **current price only** (no historical data)
- Each scrape produces 1 observation per indicator
- Time series built by daily scraping over time
- Derived metrics (MA7, MA30) appear after sufficient history

### 3. Robust Scraping
- Playwright-based headless browser
- User-agent rotation for politeness
- Retry logic with exponential backoff
- Configurable timeouts (30s default)

### 4. Bronze Structure for Scrapers
```json
{
  "rows": [
    {
      "html": "<html>...</html>",
      "url": "https://www.tgju.org/profile/price_dollar_rl",
      "scraped_at": "2026-09-08T20:15:00+03:30"
    }
  ]
}
```

---

## Architecture Decisions

### Why Synchronous Playwright?
- Simpler error handling (no async/await complexity)
- Easier testing (no pytest-asyncio)
- Sufficient for daily batch scraping
- Matches existing codebase patterns

### Why Parser/Scraper Separation?
- Unit test parser with fixture HTML (no browser)
- Website changes only affect parser
- Fast test execution (milliseconds vs seconds)
- Reusable for archived HTML

### Why Single Observation?
- TGJU reality: current price only, no archives
- Cannot backfill 30 days in one run
- Airflow accumulates observations over time
- Honest about data source limitations

---

## Testing Strategy

### Unit Tests (Fast, No Network, No DB)
- **Parser:** 45 tests with fixture HTML
- **Scraper:** 39 tests with mocked Playwright
- **Execution:** ~2 seconds total

### Integration Tests (Real DB, Fixture HTML)
- **Pipeline:** Full Bronze→Silver→Gold roundtrip
- **FK Integrity:** Silver→Bronze, Gold→Silver
- **Audit Trails:** Collection log, transformation log
- **Idempotency:** Re-run upserts Silver, republishes Gold
- **Execution:** ~6 seconds

### Live Test (Optional, Network Required)
- Hits real TGJU website
- Skipped by default
- Run manually: `RUN_LIVE_API_TESTS=1 pytest -m live`

---

## Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| No historical data | First run: 1 obs/indicator | Daily Airflow DAG accumulates |
| Market hours | Prices stale outside market | Schedule after close (11 PM) |
| Website fragility | Selector breaks on structure change | Monitor, update parser, regression test |
| Sanctions | Temporary availability gaps | Retry logic, alerts on failures |

---

## Dependencies

```toml
# Production
playwright = "^1.40.0"      # Web scraping
jdatetime = "^5.0.0"        # Persian calendar

# Development
pytest-playwright = "^0.4.4"  # Test fixtures
```

**Browser Binary:** ~200MB (auto-downloaded by `playwright install`)

---

## File Structure

```
src/connectors/
├── tgju_parser.py          # HTML parsing, Persian handling
├── tgju_scraper.py         # Playwright scraper, pipeline integration

tests/
├── fixtures/tgju/          # Captured HTML for tests
│   ├── usd_normal.html
│   ├── gold_normal.html
│   └── coin_normal.html
├── unit/connectors/
│   ├── test_tgju_parser.py       # 45 tests
│   └── test_tgju_scraper.py      # 39 tests
└── integration/
    └── test_tgju_pipeline.py     # 16 tests

docs/phase-3/
├── IMPLEMENTATION.md       # Technical details (this folder)
├── VALIDATION.md           # Validation checklist
└── README.md               # This file
```

---

## Performance

| Metric | Value |
|--------|-------|
| Browser launch | ~2s |
| Page load (per indicator) | ~1-3s |
| HTML parsing | <50ms |
| Total (3 indicators) | ~5-10s |

**Scalability:** Can handle 20+ indicators within 1-minute DAG run.

---

## Next Steps

### Remaining Phase 3 Work

**Airflow Orchestration** (estimated 1-2 days):
1. Deploy Airflow 3.x locally with LocalExecutor
2. Create daily TGJU DAG (schedule: 11 PM Tehran time, Sat-Wed)
3. Set up alerts (email + Slack on consecutive failures)
4. Test backfill strategy

### Future Phases

**Phase 4:** IMF, EIA, OPEC APIs (easier than scraping)  
**Phase 5:** CBI, SCI scrapers (reuse TGJU patterns)  
**Phase 6:** TSETMC, HBSIR data packages  
**Phase 7:** Streamlit dashboard  
**Phase 8:** Production readiness (CI/CD, monitoring)

---

## Validation Status

✅ **All Validation Criteria Met** (as of September 8, 2026)

| Criterion | Status |
|-----------|--------|
| Unit tests pass | ✅ 84/84 |
| Integration tests pass | ✅ 15/15 (1 skipped) |
| Coverage ≥ 80% | ✅ 83.06% |
| Database integrity | ✅ Verified |
| FK chains valid | ✅ Verified |
| Hypertable created | ✅ Verified |
| Audit trails | ✅ Verified |
| Idempotency | ✅ Verified |
| Code quality | ✅ Lint + typecheck pass |
| Documentation | ✅ Complete |

**See [VALIDATION.md](VALIDATION.md) for detailed steps.**

---

## Support

### Documentation
- Implementation details → [IMPLEMENTATION.md](IMPLEMENTATION.md)
- Validation steps → [VALIDATION.md](VALIDATION.md)
- Data dictionary → [../phase-2/data_dictionary.md](../phase-2/data_dictionary.md#tgju-indicators-phase-3)
- Agent guidance → [../../AGENTS.md](../../AGENTS.md) (see "Scraper-Specific Patterns")

### Common Commands
```bash
# Run all tests
make test-all

# Run only TGJU tests
poetry run pytest tests/unit/connectors/test_tgju_parser.py -v
poetry run pytest tests/unit/connectors/test_tgju_scraper.py -v
poetry run pytest tests/integration/test_tgju_pipeline.py -v

# Check coverage
make test

# Format and lint
make format
make lint

# Type check
make typecheck

# Database operations
make db-up        # Start PostgreSQL
make db-down      # Stop PostgreSQL
make db-shell     # Connect to psql
make db-reset     # Reset database (WARNING: deletes data)
```

---

## Contributors

**Phase 3 Implementation:** August 19 - September 8, 2026

---

## License

[To be determined — see main LICENSE file]
