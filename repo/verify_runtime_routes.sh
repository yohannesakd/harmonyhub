#!/usr/bin/env bash
# verify_runtime_routes.sh
#
# Optional supplementary runtime/proxy smoke verification for HarmonyHub.
#
# What this does:
#   1. Brings up the full compose stack using docker-compose.verify.yml overlay, which
#      enables demo-seed startup and activates HH_ROUTE_COVERAGE_FILE so every live
#      request through the running API is logged to apps/api/coverage/route_hits.jsonl.
#   2. Waits for the API to be ready via the live /health/ready endpoint.
#   3. Issues real HTTP requests through the TLS proxy (https://localhost:9443) using
#      demo credentials, hitting a representative cross-section of runtime endpoints.
#   4. Runs the route-coverage report generator inside the api container to produce
#      host-visible summary artifacts.
#   5. Tears down the verify stack and removes the cookie file.
#
# What this is NOT:
#   - This is NOT the canonical full test gate.  Use ./run_tests.sh for that.
#   - The artifacts are runtime/proxy smoke evidence (real HTTP through live uvicorn +
#     Nginx TLS proxy), not in-process TestClient output.
#   - It does NOT cover all 82 endpoints; it covers a representative cross-section.
#   - It is supplementary periodic verification, not a replacement for ./run_tests.sh.
#
# Host requirements: Docker, curl, POSIX shell.
# No jq, python, node, or package managers are needed on the host.
#
set -euo pipefail

PROXY_BASE="https://localhost:9443/api/v1"
COVERAGE_DIR="${PWD}/apps/api/coverage"
COOKIE_FILE="${COVERAGE_DIR}/.smoke_cookies"
HITS_FILE="${COVERAGE_DIR}/route_hits.jsonl"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.verify.yml"

# --- pre-flight -----------------------------------------------------------

if [ -n "$(docker compose ps -q 2>/dev/null)" ]; then
  echo "[verify_runtime_routes] ERROR: HarmonyHub compose stack is already running." >&2
  echo "  Bring it down first before running this helper:" >&2
  echo "    docker compose down" >&2
  exit 1
fi

mkdir -p "${COVERAGE_DIR}"
rm -f "${COOKIE_FILE}" "${HITS_FILE}"

# --- bring up verify stack ------------------------------------------------

echo "[verify_runtime_routes] Building and starting verify stack..."
# shellcheck disable=SC2086
docker compose ${COMPOSE_FILES} up -d --build

# --- wait for live API ready ----------------------------------------------

echo "[verify_runtime_routes] Waiting for API to be ready at ${PROXY_BASE}/health/ready ..."
RETRIES=40
until curl -sk -f "${PROXY_BASE}/health/ready" -o /dev/null; do
  RETRIES=$((RETRIES - 1))
  if [ "${RETRIES}" -le 0 ]; then
    echo "[verify_runtime_routes] ERROR: API did not become ready in time." >&2
    # shellcheck disable=SC2086
    docker compose ${COMPOSE_FILES} logs api | tail -30
    # shellcheck disable=SC2086
    docker compose ${COMPOSE_FILES} down
    exit 1
  fi
  sleep 5
done
echo "[verify_runtime_routes] API is ready."

# --- smoke requests through live proxy ------------------------------------
# All requests go through the TLS proxy at https://localhost:9443 (-k = accept self-signed cert).
# The running API writes each hit to /app/coverage/route_hits.jsonl via the middleware.

echo "[verify_runtime_routes] Running smoke requests through proxy..."

# Health (no auth required)
curl -sk -f -o /dev/null "${PROXY_BASE}/health/live"
curl -sk -f -o /dev/null "${PROXY_BASE}/health/ready"

# Login — establishes session cookie; no CSRF required for this endpoint
LOGIN_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" \
  -c "${COOKIE_FILE}" \
  -X POST "${PROXY_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123!"}')

if [ "${LOGIN_STATUS}" != "200" ]; then
  echo "[verify_runtime_routes] ERROR: Login returned HTTP ${LOGIN_STATUS} — demo seed may not be active." >&2
  # shellcheck disable=SC2086
  docker compose ${COMPOSE_FILES} down
  exit 1
fi
echo "[verify_runtime_routes]   POST /auth/login → ${LOGIN_STATUS}"

# Authenticated GET requests — session cookie only, no CSRF needed for reads
_smoke_get() {
  local path="${1}"
  local status
  status=$(curl -sk -o /dev/null -w "%{http_code}" \
    -b "${COOKIE_FILE}" \
    "${PROXY_BASE}${path}")
  echo "[verify_runtime_routes]   GET ${path} → ${status}"
}

_smoke_get "/auth/me"
_smoke_get "/contexts/available"
_smoke_get "/directory/search"
_smoke_get "/directory/search?q=test"
_smoke_get "/repertoire/search"
_smoke_get "/menu/items"
_smoke_get "/recommendations/directory"
_smoke_get "/recommendations/repertoire"
_smoke_get "/recommendations/config"
_smoke_get "/recommendations/featured"
_smoke_get "/pairing-rules"
_smoke_get "/addresses"
_smoke_get "/orders/mine"
_smoke_get "/operations/status"
_smoke_get "/operations/audit-events"
_smoke_get "/operations/backups/runs"
_smoke_get "/operations/exports/runs"
_smoke_get "/operations/recovery-drills"
_smoke_get "/imports/batches"
_smoke_get "/imports/duplicates"
_smoke_get "/accounts/users"
_smoke_get "/admin/policies/abac/surfaces"
_smoke_get "/admin/policies/abac/rules"

echo "[verify_runtime_routes] Smoke requests done."

# --- generate report inside container ------------------------------------
# Python runs inside the api image — no host Python needed.
# /app/coverage is the same host-visible path as ${COVERAGE_DIR}.

echo "[verify_runtime_routes] Generating route-hit report..."
# shellcheck disable=SC2086
docker compose ${COMPOSE_FILES} run --rm --no-deps \
  -v "${PWD}/apps/api:/workspace" \
  api python /workspace/scripts/generate_route_coverage_report.py \
    --hits-file /app/coverage/route_hits.jsonl \
    --output-json /app/coverage/runtime-smoke-coverage.json \
    --output-md /app/coverage/runtime-smoke-coverage.md

# --- tear down ------------------------------------------------------------

rm -f "${COOKIE_FILE}"

echo "[verify_runtime_routes] Bringing down verify stack..."
# shellcheck disable=SC2086
docker compose ${COMPOSE_FILES} down

# --- summary --------------------------------------------------------------

echo ""
echo "[verify_runtime_routes] Runtime smoke verification complete."
echo "  Artifacts written to apps/api/coverage/:"
echo "    route_hits.jsonl               — raw per-request JSONL from the live API middleware"
echo "    runtime-smoke-coverage.json    — structured route-hit inventory"
echo "    runtime-smoke-coverage.md      — human-readable route-hit summary"
echo ""
echo "  IMPORTANT: these artifacts are from real HTTP requests through the live uvicorn"
echo "  process and Nginx TLS proxy.  They are supplementary smoke evidence, not a"
echo "  replacement for ./run_tests.sh (the full canonical test gate)."
