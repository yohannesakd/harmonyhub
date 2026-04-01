#!/usr/bin/env bash
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-harmonyhub}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-harmonyhub_dev}"
API_TEST_DB_NAME="${HH_API_TEST_DB_NAME:-harmonyhub_test}"
API_TEST_DATABASE_URL="${HH_API_TEST_DATABASE_URL:-postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${API_TEST_DB_NAME}}"

echo "[run_tests] Starting PostgreSQL service for API tests"
docker compose up -d --wait db >/dev/null

echo "[run_tests] Resetting PostgreSQL API test database (${API_TEST_DB_NAME})"
docker compose exec -T db psql -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"${API_TEST_DB_NAME}\";" \
  -c "CREATE DATABASE \"${API_TEST_DB_NAME}\";" >/dev/null

echo "[run_tests] Building test images"
docker compose build api worker web >/dev/null

echo "[run_tests] Running API tests"
docker compose run --rm --no-deps \
  -e DATABASE_URL="${API_TEST_DATABASE_URL}" \
  -e HH_TEST_POSTGRES_DATABASE_URL="${API_TEST_DATABASE_URL}" \
  -e HH_COOKIE_SECURE=false \
  -e HH_BACKUP_NIGHTLY_ENABLED=false \
  api pytest -q

echo "[run_tests] Running Worker tests"
docker compose run --rm --no-deps worker pytest -q

echo "[run_tests] Running Web tests"
docker compose run --rm --no-deps web npm run test -- --run

echo "[run_tests] All tests passed"
