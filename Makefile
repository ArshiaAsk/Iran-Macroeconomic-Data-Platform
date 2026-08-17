.PHONY: help format lint typecheck test test-unit test-integration test-all check db-up db-down db-shell db-reset db-check install clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with Poetry
	poetry install

format: ## Format code with ruff
	poetry run ruff format .

lint: ## Lint code with ruff
	poetry run ruff check .

typecheck: ## Run type checking with mypy
	poetry run mypy src/

test: ## Run unit tests with coverage (skips integration; use test-all for everything)
	poetry run pytest -m "not integration"

test-unit: ## Run unit tests only
	poetry run pytest tests/unit/ -v

# The 80% gate measures the project as a whole, so a subset run must not be
# judged by it -- test and test-all enforce it.
test-integration: ## Run integration tests (requires Docker)
	poetry run pytest tests/integration/ -m integration -v --cov-fail-under=0

test-all: ## Run unit + integration tests (requires Docker)
	poetry run pytest

check: format lint typecheck test ## Run all quality gates

db-up: ## Start Docker services (PostgreSQL + TimescaleDB)
	docker compose up -d
	@echo "Waiting for database to be ready..."
	@sleep 5
	@docker compose exec postgres pg_isready -U iran_macro -d iran_macro_db

db-down: ## Stop Docker services
	docker compose down

db-shell: ## Connect to PostgreSQL shell
	docker compose exec postgres psql -U iran_macro -d iran_macro_db

db-reset: ## Reset database (WARNING: deletes all data)
	docker compose down -v
	docker compose up -d
	@echo "Database reset complete. Run 'alembic upgrade head' to recreate tables."

db-check: ## Check database connection and TimescaleDB status
	@echo "Testing database connection..."
	@docker compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT version();" > /dev/null && echo "✓ Database connection successful" || echo "✗ Database connection failed"
	@echo "Checking TimescaleDB extension..."
	@docker compose exec postgres psql -U iran_macro -d iran_macro_db -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';" | grep timescaledb && echo "✓ TimescaleDB extension installed" || echo "✗ TimescaleDB extension not found"

clean: ## Remove generated files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleanup complete"
