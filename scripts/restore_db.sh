#!/usr/bin/env bash
#
# Restore a pg_dump -Fc archive produced by scripts/backup_db.sh into a
# TimescaleDB database, following the documented TimescaleDB logical-restore
# procedure:
#
#   CREATE DATABASE <target>;
#   CREATE EXTENSION IF NOT EXISTS timescaledb;   -- must exist before restore
#   SELECT timescaledb_pre_restore();
#   pg_restore -Fc -d <target> <file>;            -- NEVER with -j
#   SELECT timescaledb_post_restore();
#
# `-j` is deliberately never passed: a parallel restore cannot correctly restore
# the TimescaleDB catalog. The target is a **scratch** database by default
# (iran_macro_restore_test); restoring over the live database requires --force.
#
# Usage:
#   bash scripts/restore_db.sh backups/<name>.bak
#   bash scripts/restore_db.sh backups/<name>.bak --target my_scratch_db
#   bash scripts/restore_db.sh backups/<name>.bak --force   # live target, careful
#
# Connection settings come from .env (or the environment): DATABASE_NAME,
# DATABASE_USER, DATABASE_HOST, DATABASE_PORT, DATABASE_PASSWORD.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

usage() {
  echo "usage: $0 <backup-file> [--target DB] [--force]" >&2
}

BACKUP_FILE=""
TARGET_OVERRIDE=""
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target|-t)
      TARGET_OVERRIDE="${2:-}"
      shift 2
      ;;
    --force|-f)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "${BACKUP_FILE}" ]]; then
        BACKUP_FILE="$1"
      else
        echo "error: unexpected argument '$1'" >&2
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "${BACKUP_FILE}" ]]; then
  usage
  exit 1
fi
if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "error: backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

LIVE_DB="${DATABASE_NAME:-iran_macro_db}"
DB_USER="${DATABASE_USER:-iran_macro}"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
TARGET_DB="${TARGET_OVERRIDE:-${TARGET_DB:-iran_macro_restore_test}}"

if [[ "${TARGET_DB}" == "${LIVE_DB}" && "${FORCE}" -ne 1 ]]; then
  echo "error: refusing to restore over the live database '${LIVE_DB}'." >&2
  echo "       Restore into a scratch database, or pass --force to overwrite it." >&2
  exit 1
fi

BACKUP_BASENAME="$(basename "${BACKUP_FILE}")"

container_running() {
  docker compose ps -q postgres 2>/dev/null | grep -q .
}

if container_running; then
  echo "Restoring ${BACKUP_BASENAME} into '${TARGET_DB}' via the postgres container..."
  docker compose cp "${BACKUP_FILE}" "postgres:/tmp/${BACKUP_BASENAME}"

  psql_target() {
    docker compose exec -T postgres psql -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 "$@"
  }
  psql_admin() {
    docker compose exec -T postgres psql -U "${DB_USER}" -d postgres -v ON_ERROR_STOP=1 "$@"
  }

  psql_admin -c "DROP DATABASE IF EXISTS \"${TARGET_DB}\";" >/dev/null
  psql_admin -c "CREATE DATABASE \"${TARGET_DB}\";" >/dev/null
  # The extension must exist on the target before the restore (and before
  # timescaledb_pre_restore); a missing extension is the documented restore
  # failure this ordering prevents.
  psql_target -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null
  psql_target -c "SELECT timescaledb_pre_restore();" >/dev/null
  # No -j: a parallel restore cannot correctly restore the TimescaleDB catalog.
  docker compose exec -T postgres \
    pg_restore -U "${DB_USER}" -d "${TARGET_DB}" --no-owner --no-privileges \
    "/tmp/${BACKUP_BASENAME}"
  psql_target -c "SELECT timescaledb_post_restore();" >/dev/null

  docker compose exec -T postgres rm -f "/tmp/${BACKUP_BASENAME}"

  echo "Row counts in '${TARGET_DB}':"
  docker compose exec -T postgres psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc "
    SELECT 'bronze.bronze_raw=' || count(*) FROM bronze.bronze_raw
    UNION ALL SELECT 'silver.silver_cleaned=' || count(*) FROM silver.silver_cleaned
    UNION ALL SELECT 'gold.gold_analytical=' || count(*) FROM gold.gold_analytical
    UNION ALL SELECT 'metadata.indicator_catalog=' || count(*) FROM metadata.indicator_catalog
    UNION ALL SELECT 'metadata.data_collection_log=' || count(*) FROM metadata.data_collection_log;"
  echo "Hypertables in '${TARGET_DB}':"
  docker compose exec -T postgres psql -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT hypertable_schema || '.' || hypertable_name FROM timescaledb_information.hypertables;"
elif command -v pg_restore >/dev/null 2>&1; then
  echo "Container not running; restoring through ${DB_HOST}:${DB_PORT}..."
  export PGPASSWORD="${DATABASE_PASSWORD:-}"
  dropdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" --if-exists "${TARGET_DB}"
  createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${TARGET_DB}"
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 \
    -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 \
    -c "SELECT timescaledb_pre_restore();" >/dev/null
  pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" \
    --no-owner --no-privileges "${BACKUP_FILE}"
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 \
    -c "SELECT timescaledb_post_restore();" >/dev/null

  echo "Row counts in '${TARGET_DB}':"
  psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -tAc "
    SELECT 'bronze.bronze_raw=' || count(*) FROM bronze.bronze_raw
    UNION ALL SELECT 'silver.silver_cleaned=' || count(*) FROM silver.silver_cleaned
    UNION ALL SELECT 'gold.gold_analytical=' || count(*) FROM gold.gold_analytical
    UNION ALL SELECT 'metadata.indicator_catalog=' || count(*) FROM metadata.indicator_catalog
    UNION ALL SELECT 'metadata.data_collection_log=' || count(*) FROM metadata.data_collection_log;"
else
  echo "error: no running postgres service and no host pg_restore found" >&2
  echo "       start the database with 'make db-up' or install the PostgreSQL client" >&2
  exit 1
fi

echo "Restore complete: '${TARGET_DB}'."
