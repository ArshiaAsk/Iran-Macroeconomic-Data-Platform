#!/usr/bin/env bash
#
# Back up the TimescaleDB database to backups/<name>.bak with pg_dump -Fc.
#
# The dump is a custom-format archive (-Fc) because that is the form the
# documented TimescaleDB logical-backup procedure restores with pg_restore (and
# the form that supports selective/parallel restore). It is written inside the
# running `postgres` service container and copied out, so a host PostgreSQL
# client is not required; when the container is not running and a host
# pg_dump exists, the script falls back to dumping through the published port.
#
# Connection settings come from .env (or the environment): DATABASE_NAME,
# DATABASE_USER, DATABASE_HOST, DATABASE_PORT, DATABASE_PASSWORD.
#
# Usage:
#   bash scripts/backup_db.sh                 # writes backups/<db>_<utc>.bak
#   BACKUP_DIR=/tmp/dumps bash scripts/backup_db.sh
#
# The PostgreSQL and TimescaleDB versions are recorded in a <name>.bak.meta
# sidecar: a version mismatch is the documented cause of a failed restore.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Load .env without overriding anything already exported.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DB_NAME="${DATABASE_NAME:-iran_macro_db}"
DB_USER="${DATABASE_USER:-iran_macro}"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE_NAME="${DB_NAME}_${TIMESTAMP}.bak"
mkdir -p "${BACKUP_DIR}"
DEST="${BACKUP_DIR}/${FILE_NAME}"

if [[ -e "${DEST}" ]]; then
  echo "error: refusing to overwrite existing backup ${DEST}" >&2
  exit 1
fi

container_running() {
  docker compose ps -q postgres 2>/dev/null | grep -q .
}

if container_running; then
  echo "Backing up ${DB_NAME} via the postgres service container..."
  docker compose exec -T postgres \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc -f "/tmp/${FILE_NAME}"
  docker compose cp "postgres:/tmp/${FILE_NAME}" "${DEST}"
  docker compose exec -T postgres rm -f "/tmp/${FILE_NAME}"

  DUMP_VERSION="$(docker compose exec -T postgres pg_dump --version | awk '{print $NF}')"
  PG_VERSION="$(docker compose exec -T postgres \
    psql -U "${DB_USER}" -d "${DB_NAME}" -tAc 'SHOW server_version;' | tr -d '[:space:]')"
  TS_VERSION="$(docker compose exec -T postgres \
    psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
    "SELECT extversion FROM pg_extension WHERE extname='timescaledb';" | tr -d '[:space:]')"
elif command -v pg_dump >/dev/null 2>&1; then
  echo "Container not running; dumping ${DB_NAME} through ${DB_HOST}:${DB_PORT}..."
  PGPASSWORD="${DATABASE_PASSWORD:-}" pg_dump \
    -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -Fc -f "${DEST}"
  DUMP_VERSION="$(pg_dump --version | awk '{print $NF}')"
  PG_VERSION="$(PGPASSWORD="${DATABASE_PASSWORD:-}" psql \
    -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -tAc 'SHOW server_version;' | tr -d '[:space:]')"
  TS_VERSION="$(PGPASSWORD="${DATABASE_PASSWORD:-}" psql \
    -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -tAc \
    "SELECT extversion FROM pg_extension WHERE extname='timescaledb';" | tr -d '[:space:]')"
else
  echo "error: no running postgres service and no host pg_dump found" >&2
  echo "       start the database with 'make db-up' or install the PostgreSQL client" >&2
  exit 1
fi

cat >"${DEST}.meta" <<EOF
database=${DB_NAME}
created_at=${TIMESTAMP}
postgres_version=${PG_VERSION}
timescaledb_version=${TS_VERSION}
pg_dump_version=${DUMP_VERSION}
EOF

echo "Backup written: ${DEST}"
echo "  PostgreSQL ${PG_VERSION} / TimescaleDB ${TS_VERSION} (pg_dump ${DUMP_VERSION})"
ls -lh "${DEST}"
