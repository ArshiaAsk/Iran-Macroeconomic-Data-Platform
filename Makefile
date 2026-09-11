.PHONY: help format lint typecheck test test-unit test-integration test-all check db-up db-down db-shell db-reset db-check install clean dashboard airflow-init airflow-up airflow-down airflow-status airflow-logs

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

dashboard: ## Launch the local Streamlit dashboard
	poetry run streamlit run dashboard/app.py

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

airflow-init: ## Initialize Airflow database and display credentials
	@echo "Setting up Airflow environment..."
	@export $$(cat airflow/config/airflow.env | grep -v '^#' | xargs) && \
		poetry run airflow db migrate
	@echo "✓ Airflow initialized."
	@echo ""
	@echo "======================================================================"
	@echo "Airflow Simple Auth Manager Credentials:"
	@echo "======================================================================"
	@echo "Web UI: http://localhost:8080"
	@echo ""
	@if [ -f airflow/simple_auth_manager_passwords.json ]; then \
		echo "Admin User:"; \
		echo "  Username: admin"; \
		echo "  Password: $$(cat airflow/simple_auth_manager_passwords.json | grep -o '"admin": "[^"]*"' | cut -d'"' -f4)"; \
		echo ""; \
		echo "Viewer User:"; \
		echo "  Username: viewer"; \
		echo "  Password: $$(cat airflow/simple_auth_manager_passwords.json | grep -o '"viewer": "[^"]*"' | cut -d'"' -f4)"; \
	else \
		echo "Password file not found. Start Airflow with 'make airflow-up' to generate."; \
	fi
	@echo "======================================================================"

airflow-up: ## Start Airflow webserver and scheduler (runs in foreground; Ctrl+C to stop, or use make airflow-down from another terminal)
	@echo "Starting Airflow services..."
	@exec bash -c 'set -m; \
		export $$(cat airflow/config/airflow.env | grep -v "^#" | xargs); \
		cleanup() { \
			echo ""; \
			echo "Shutting down Airflow..."; \
			if [ -f airflow/airflow-standalone.pid ]; then \
				AIRFLOW_PID=$$(cat airflow/airflow-standalone.pid); \
				if [ -n "$$AIRFLOW_PID" ] && ps -p $$AIRFLOW_PID > /dev/null 2>&1; then \
					kill -TERM -$$AIRFLOW_PID 2>/dev/null || true; \
					sleep 2; \
					kill -KILL -$$AIRFLOW_PID 2>/dev/null || true; \
				fi; \
				rm -f airflow/airflow-standalone.pid; \
			fi; \
			echo "✓ Airflow stopped"; \
		}; \
		trap cleanup EXIT INT TERM; \
		poetry run airflow standalone & \
		AIRFLOW_PID=$$!; \
		echo $$AIRFLOW_PID > airflow/airflow-standalone.pid; \
		echo ""; \
		echo "✓ Airflow started in standalone mode."; \
		echo "  Web UI: http://localhost:8080"; \
		echo "  Check '\''airflow/simple_auth_manager_passwords.json'\'' for credentials"; \
		echo "  Stop with: make airflow-down or press Ctrl+C"; \
		wait $$AIRFLOW_PID'

airflow-down: ## Stop Airflow services
	@echo "Stopping Airflow services..."
	@if [ -f airflow/airflow-standalone.pid ]; then \
		AIRFLOW_PID=$$(cat airflow/airflow-standalone.pid); \
		if ps -p $$AIRFLOW_PID > /dev/null 2>&1; then \
			echo "Terminating Airflow process tree (PID: $$AIRFLOW_PID)..."; \
			kill -TERM -$$AIRFLOW_PID 2>/dev/null || true; \
			for i in 1 2 3 4 5; do \
				if ! ps -p $$AIRFLOW_PID > /dev/null 2>&1; then \
					break; \
				fi; \
				sleep 1; \
			done; \
			if ps -p $$AIRFLOW_PID > /dev/null 2>&1; then \
				echo "Force killing Airflow process tree..."; \
				kill -KILL -$$AIRFLOW_PID 2>/dev/null || true; \
			fi; \
		else \
			echo "Airflow process (PID: $$AIRFLOW_PID) not running"; \
		fi; \
		rm -f airflow/airflow-standalone.pid; \
	else \
		echo "No PID file found. Attempting to stop by pattern matching..."; \
		pkill -TERM -f "airflow scheduler" 2>/dev/null || true; \
		sleep 2; \
		pkill -KILL -f "airflow scheduler" 2>/dev/null || true; \
		pkill -KILL -f "airflow worker" 2>/dev/null || true; \
	fi
	@echo "✓ Airflow stopped"

airflow-status: ## Check Airflow DAGs status
	@export $$(cat airflow/config/airflow.env | grep -v '^#' | xargs) && \
		poetry run airflow dags list

airflow-logs: ## View Airflow logs
	@tail -f airflow/logs/*/*.log 2>/dev/null || echo "No logs found yet"
