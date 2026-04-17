#!/usr/bin/env bash
set -euo pipefail

POSTGRES_DB="${POSTGRES_DB:-harmonyhub}"
POSTGRES_USER="${POSTGRES_USER:-harmonyhub}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-harmonyhub_dev}"

APP_DB_NAME="${HH_APP_DB_NAME:-$POSTGRES_DB}"
TEST_DB_NAME="${HH_API_TEST_DB_NAME:-harmonyhub_test}"

INIT_TEST_DB="${HH_INIT_DB_INCLUDE_TEST_DB:-true}"
MIGRATE_TEST_DB="${HH_INIT_DB_MIGRATE_TEST_DB:-false}"

APP_DATABASE_URL="${HH_INIT_DB_DATABASE_URL:-postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${APP_DB_NAME}}"
TEST_DATABASE_URL="${HH_INIT_DB_TEST_DATABASE_URL:-postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${TEST_DB_NAME}}"

validate_db_name() {
  local db_name="$1"
  if [[ ! "$db_name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "[init_db] Invalid PostgreSQL database name: ${db_name}" >&2
    echo "[init_db] Allowed pattern: ^[A-Za-z_][A-Za-z0-9_]*$" >&2
    exit 1
  fi
}

ensure_database_exists() {
  local db_name="$1"
  validate_db_name "$db_name"
  docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL >/dev/null
SELECT 'CREATE DATABASE "${db_name}"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')
\gexec
SQL
}

run_alembic_upgrade() {
  local db_url="$1"
  docker compose run --rm --no-deps -e DATABASE_URL="$db_url" api alembic upgrade head >/dev/null
}

echo "[init_db] Starting PostgreSQL service"
docker compose up -d --wait db >/dev/null

echo "[init_db] Ensuring application database exists (${APP_DB_NAME})"
ensure_database_exists "$APP_DB_NAME"

if [[ "$INIT_TEST_DB" == "true" ]]; then
  echo "[init_db] Ensuring API test database exists (${TEST_DB_NAME})"
  ensure_database_exists "$TEST_DB_NAME"
fi

echo "[init_db] Building API image for migration tooling"
docker compose build api >/dev/null

echo "[init_db] Running Alembic migrations on application database"
run_alembic_upgrade "$APP_DATABASE_URL"

if [[ "$INIT_TEST_DB" == "true" && "$MIGRATE_TEST_DB" == "true" ]]; then
  echo "[init_db] Running Alembic migrations on API test database"
  run_alembic_upgrade "$TEST_DATABASE_URL"
fi

echo "[init_db] Database setup complete"
