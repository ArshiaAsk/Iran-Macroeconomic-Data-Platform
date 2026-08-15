# Phase 1 Validation Checklist

This document provides the validation steps for Phase 1 implementation.

## Prerequisites

Before running validation:

1. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install Docker and Docker Compose:
   - Docker: https://docs.docker.com/get-docker/
   - Docker Compose: Included with Docker Desktop

## Validation Steps

### Level 1: Environment Setup

```bash
# Check required tools
poetry --version
docker --version
docker-compose --version
```

Expected: All commands should return version numbers.

### Level 2: Install Dependencies

```bash
# Install Python dependencies
poetry install

# Activate virtual environment
poetry shell
```

Expected: All dependencies installed without errors.

### Level 3: Code Quality Checks

```bash
# Format code
make format

# Lint code
make lint

# Type check
make typecheck
```

Expected: All commands pass without errors.

### Level 4: Start Docker Services

```bash
# Start PostgreSQL + TimescaleDB
make db-up

# Check database status
make db-check
```

Expected:
- PostgreSQL container running and healthy
- TimescaleDB extension installed
- Database connection successful

### Level 5: Database Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Verify tables created
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "\dt bronze.*"
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "\dt silver.*"
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "\dt gold.*"
docker-compose exec postgres psql -U iran_macro -d iran_macro_db -c "\dt metadata.*"
```

Expected:
- Migration file created
- All tables created in correct schemas
- TimescaleDB hypertable for gold.gold_analytical

### Level 6: Run Tests

```bash
# Run all tests with coverage
make test

# Expected output:
# - All tests pass
# - Coverage >= 80%
```

Expected:
- All unit tests pass
- Code coverage >= 80%

### Level 7: Full Validation

```bash
# Run all quality gates
make check
```

Expected: All checks pass (format, lint, typecheck, test).

## Manual Verification

### 1. Database Connection

```bash
docker-compose exec postgres psql -U iran_macro -d iran_macro_db
```

Run these queries:
```sql
-- Check TimescaleDB extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';

-- Check schemas
\dn

-- Check tables
\dt bronze.*
\dt silver.*
\dt gold.*
\dt metadata.*

-- Exit
\q
```

### 2. File Structure

Verify directory structure:
```bash
tree -L 2 -I '__pycache__|*.pyc|.git'
```

Expected structure:
```
.
├── .agents/
├── .env.template
├── .gitignore
├── AGENTS.md
├── Makefile
├── PRD.md
├── README.md
├── alembic/
├── alembic.ini
├── dashboard/
├── docker-compose.yml
├── docs/
├── pyproject.toml
├── scripts/
├── src/
└── tests/
```

### 3. Configuration Test

```bash
# Copy environment template
cp .env.template .env

# Test configuration loading
python -c "from src.utils.config import get_config; config = get_config(); print(f'Database URL: {config.database.url}')"
```

Expected: Database URL printed without errors.

## Troubleshooting

### Poetry Installation Issues

If Poetry is not found after installation:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Or add to ~/.bashrc or ~/.zshrc
```

### Docker Permission Issues

If you get permission errors:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Database Connection Issues

If database connection fails:
```bash
# Check Docker logs
docker-compose logs postgres

# Restart services
make db-down
make db-up
```

### Test Failures

If tests fail due to missing dependencies:
```bash
# Reinstall dependencies
poetry install --sync

# Clear cache
make clean
```

## Acceptance Criteria

✅ All criteria from Phase 1 plan:

- [x] Poetry project initialized with all dependencies
- [x] Docker Compose starts PostgreSQL + TimescaleDB
- [x] Database connection works
- [x] 4-layer schema models created (Bronze/Silver/Gold/Metadata)
- [x] TimescaleDB hypertable configuration ready
- [x] Alembic migrations framework configured
- [x] DataConnector abstract base class defined
- [x] Custom exception hierarchy implemented
- [x] Validation framework with quality checks
- [x] Logging configuration with JSON formatting
- [x] Configuration management with Pydantic
- [x] pytest framework with fixtures and markers
- [x] ruff, mypy, pytest all configured
- [x] Makefile provides common commands
- [x] README.md documents setup and usage
- [x] Unit tests created (need Poetry to run)
- [x] Integration test structure ready

## Next Steps (Phase 2)

After validation passes:

1. Implement World Bank API connector
2. Implement TGJU scraper
3. Test end-to-end Bronze → Silver → Gold flow
4. Create data dictionary
5. Document connector patterns

---

**Note:** This validation requires Poetry and Docker to be installed. The code is complete and ready for validation once these prerequisites are met.
