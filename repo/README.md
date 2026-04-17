# HarmonyHub (Auth + Discovery + Ordering/Scheduling + Fulfillment/Handoff + Imports/Account Controls + Offline Sync/Conflict UX + Operations Accountability)

**Project type: fullstack** (Vue 3 SPA + FastAPI REST API + PostgreSQL + background worker, all containerised under Docker Compose)

HarmonyHub is a multi-tenant web platform for performing arts operations and event concessions.

This repository currently contains:

- dockerized runtime baseline (Vue + FastAPI + PostgreSQL + worker + HTTPS proxy)
- implemented slices for:
  - authentication/session/security baseline
  - active tenant context + RBAC default-deny + ABAC foundation
  - directory/repertoire data model + scoped search APIs + masked contact reveal flow
  - recommendation scoring/configuration + featured pins + pairing controls
  - concession ordering + scheduling (pickup/delivery checkout, address book, ZIP zones, slot capacities)
  - fulfillment + handoff operations (operator queues, service-aware transitions, pickup-code verification)
  - imports + merge review + account controls (secure uploads, CSV normalization/apply, duplicate merge/undo, freeze/unfreeze)
  - offline sync + conflict UX (cached safe reads, protected queued writes, reconnect retry, queued-action conflict review)
  - operations accountability (audit query UI/API, directory exports, backup runs, recovery drill records, status board)

## Repository layout

```text
repo/
  apps/
    api/      # FastAPI app + Alembic + pytest
    web/      # Vue 3 app + Pinia + Vitest + Playwright
    worker/   # Background worker + pytest
  infra/
    proxy/    # Nginx TLS proxy + self-signed cert bootstrap
  docker-compose.yml
  init_db.sh
  run_tests.sh
```

## Implemented capabilities (current)

### API core

- Session login/logout/me endpoints
- Argon2 password verification and lockout policy (5 failures -> 15-minute lock)
- CSRF validation for browser mutating routes
- Replay protection for protected mutating routes (`X-Request-Nonce`, `X-Request-Timestamp`, 5-minute window)
- Context listing and active context switching
- Dashboard endpoint bound to active context
- Directory search/detail/reveal endpoints with real context scoping and filter support
- Repertoire search/detail endpoints with linked actor/tag/region/availability filters
- Recommendation endpoints for directory and repertoire surfaces with real scoring inputs:
  - popularity over 30 days
  - recent activity over 72 hours
  - tag matching
  - runtime search impressions from `/directory/search` and `/repertoire/search` are persisted as recommendation signals
- Recommendation config APIs with scope inheritance/override (`organization -> program -> event/store`)
- Featured pin management APIs (pin/unpin/list)
- Pairing rule APIs (allowlist/blocklist/list/delete), with blocklist precedence
- RBAC default-deny authorization guards
- ABAC foundation:
  - per-surface enable/disable
  - scoped allow/deny rules with priority
  - subject/resource dimensions (`department`, `grade`, `class`) plus optional `resource_field`
  - policy simulation endpoint
- Optional TOTP MFA setup/verify/enable; MFA challenge on login when enabled
- Audit event persistence for directory contact reveal actions
- Secure upload endpoint with extension+MIME+magic-byte checks and 25MB cap
- CSV import batch pipeline for member/roster data with raw-row preservation
- Duplicate candidate queue with merge/ignore and safe undo behavior
- Membership-scoped account freeze/unfreeze APIs with reason tracking + audit events and protected-route enforcement
- Operations accountability APIs:
  - audit event query with scoped filters
  - enforced 12-month audit retention cleanup (startup + worker compliance job)
  - directory CSV export generation/list/download with scope + ABAC row/field parity against directory surfaces, requester-scoped run visibility/download
  - export CSV artifacts are encrypted at rest on disk and decrypted only for authorized download responses
  - backup run trigger/list with checksums + optional offline-medium copy verification
  - backup JSON artifacts (including offline-medium copies) are encrypted at rest on disk and decrypted only during checksum-verified restore/recovery paths
  - backup artifacts are restore-capable tenant logical snapshots over critical scoped tables
  - recovery drill create/list linked to backup runs, with PostgreSQL-schema restore verification (SQLite fallback in local/test) + table-count checks
  - operations status summary endpoint with quarterly drill compliance (`current|overdue`) and retention telemetry
- PostgreSQL storage architecture alignment:
  - flexible document columns use PostgreSQL `JSONB` in canonical runtime
  - SQLite test/local path keeps JSON compatibility
  - sensitive import-normalization payloads (`raw_row_json`, `normalized_json`) are persisted as encrypted JSON envelopes inside the flexible document columns (not plaintext JSON)
  - `recommendation_signals` is range-partitioned by `occurred_at` in PostgreSQL migrations
  - high-volume recommendation signal indexes explicitly cover `repertoire_item_id + occurred_at` and `user_id + occurred_at`
- Offline web foundation:
  - service-worker caching for app-shell/static assets only (no user API payload service-worker caching)
  - cached session/bootstrap fallback for offline read-only continuity (encrypted at rest for cached `/auth/me` payload; requires session key material to decrypt)
  - cached directory/repertoire search fallback per user+active-context+filter scope when network reads fail
  - sensitive queued payloads are encrypted at rest in browser storage for address/draft actions

### Frontend core

- Login flow with MFA challenge prompt
- Session bootstrap from `/auth/me`
- Context switcher integrated in app shell
- Dashboard view rendering active role, permissions, and ABAC enforcement state
- Directory page with usable filters, masked contact cards, reveal actions, loading/error/empty states
- Roster visibility page for referee/staff/admin roles with limited roster context surface
- Repertoire page with real search filters and results
- Recommendation rails on directory/repertoire pages
- Recommendation management page with scope config + pairing rule controls for recommendation-manage roles
- Ordering page for students/referees/staff/admin:
  - menu loading + draft creation/update
  - pickup/delivery selection
  - user-scoped address-book CRUD
  - quote and finalize flows with server-authoritative slot capacity checks
  - conflict handling with suggested next slots
  - order history and ETA summary
- Staff/admin scheduling controls:
  - ZIP delivery zone fee management
  - 15-minute slot capacity management
- Fulfillment module (staff/admin):
  - dedicated pickup and delivery operator queues
  - service-type-aware state transitions after confirmation
  - rotating pickup-code verification endpoint for pickup handoff
  - delivery dispatch/completion progression
  - queue-driven ETA updates as fulfillment status changes
- Imports/admin module (staff/admin):
  - CSV batch upload + normalize/apply workflow
  - duplicate review queue with merge/ignore/undo controls
  - organization-scoped account freeze/unfreeze controls with reason prompts
- Operations module (staff/admin):
  - status summary, latest backup/drill visibility, and quarterly drill compliance status
  - directory export trigger and run list/download access
  - manual backup trigger with offline-copy toggle and run history
  - recovery drill execution (restore verification) + drill history
  - audit event querying with filters
- Policy management module (admin):
  - ABAC surface enable/disable controls
  - scoped ABAC rule list/create/delete controls, including subject/resource dimensions and field constraints
  - ABAC simulation controls and decision output display for context + subject/resource dimensions
- Offline UX module:
  - visible sync queue states (`local_queued`, `syncing`, `failed_retrying`, `conflict`)
  - per-item sync indicators on address and order rows
  - queued confirm conflict surfacing with server-provided conflict reasons and suggested slot context

### Seed baseline users (optional startup demo seed)

- `admin` / `admin123!`
- `staff` / `staff123!`
- `referee` / `ref123!`
- `student` / `stud123!`

`admin` has administrator memberships across multiple contexts; other users are role-specific.

Startup seeding is disabled by default. To opt into demo seeding on API startup for local development,
set `HH_DEMO_SEED_ON_STARTUP=true` in a development/test environment.

For non-development environments, startup demo seeding is intentionally skipped even when
`HH_DEMO_SEED_ON_STARTUP=true`. Also override at least `HH_JWT_SECRET`, `HH_DATA_ENCRYPTION_KEY`, and
`HH_BOOTSTRAP_ADMIN_PASSWORD`.

## Quick reference

| What | Where |
|---|---|
| **Start the app** | `docker compose up --build` |
| **Access the app** | `https://localhost:9443` (self-signed TLS) |
| **API base** | `https://localhost:9443/api/v1` |
| **Run all tests** | `./run_tests.sh` |
| **Demo login** | `admin` / `admin123!` (see credentials below) |

## Runtime (canonical)

The project uses Docker Compose as the runtime contract.

```bash
docker compose up --build
```

Legacy CLI compatibility: `docker-compose up --build` works identically on installations that use the older hyphenated Docker Compose v1 syntax.

Compose project name is pinned to `harmonyhub` in `docker-compose.yml`.

Services started:

- `db` (PostgreSQL)
- `api` (FastAPI, runs Alembic upgrade on startup)
- `worker` (background jobs)
- `web` (Vite production preview server)
- `proxy` (TLS ingress)

The `api` service automatically runs `alembic upgrade head` on startup, so no separate database initialisation step is required for ordinary startup.

### Access points

- App (HTTPS): `https://localhost:9443` ← **primary access point**
- HTTP redirect: `http://localhost:9080`
- API base via proxy: `https://localhost:9443/api/v1`
- Direct web preview (Vite dev server, optional): `http://localhost:5173`

## Database setup (optional maintenance / CI helper)

`./init_db.sh` is **not required for ordinary startup**. `docker compose up --build` handles database initialisation automatically via the `api` service's Alembic startup step.

Use `./init_db.sh` when you need to pre-create or reset the application and test databases outside of a full compose startup — for example, before running `./run_tests.sh` on a fresh machine where the `harmonyhub_test` database does not yet exist.

```bash
./init_db.sh
```

What it does:

- starts `db` with Docker Compose
- ensures the application database exists (default: `harmonyhub`)
- ensures the API test database exists (default: `harmonyhub_test`)
- builds the `api` image and runs `alembic upgrade head` against the application database

Optional knobs:

- `HH_INIT_DB_INCLUDE_TEST_DB=false` to skip creating the test database
- `HH_INIT_DB_MIGRATE_TEST_DB=true` to also run Alembic migrations on the test database
- `HH_APP_DB_NAME`, `HH_API_TEST_DB_NAME` to override database names
- `HH_INIT_DB_DATABASE_URL`, `HH_INIT_DB_TEST_DATABASE_URL` to override migration URLs

## Testing (canonical)

```bash
./run_tests.sh
```

This script builds the service images and runs:

- API pytest suite against a dedicated PostgreSQL test database (`harmonyhub_test` by default)
- Worker pytest suite
- Web Vitest suite

API tests also include migration-path verification (`test_startup_seed_and_migrations.py`) that runs
`alembic upgrade head` and asserts key schema contracts to catch ORM-vs-migration drift.

### Browser E2E verification (Playwright — optional, separate from `./run_tests.sh`)

Playwright E2E tests are **not** part of the canonical `./run_tests.sh` gate. They require the full compose runtime to be running and a host-installed browser. They are supplementary verification only.

From `apps/web` (with the compose stack already up):

```bash
npm run test:e2e
```

Notes:

- Browser E2E runs against the compose runtime (default web base `http://127.0.0.1:5173`).
- API-side setup used by E2E helpers targets `https://localhost:9443` by default.
- To override API helper target, set `E2E_API_BASE_URL`.
- Generated artifacts are written to `apps/web/e2e-artifacts/` when the command is run:
  - HTML report: `playwright-report/`
  - Test output (screenshots/traces/videos): `test-results/`
  - Checkpoint screenshots: `screenshots/`

### API route coverage inventory artifact

Generate a concrete route-to-test coverage artifact from real endpoint hits during API pytest:

```bash
docker compose up -d db
docker compose exec -T db psql -U "${POSTGRES_USER:-harmonyhub}" -d postgres -v ON_ERROR_STOP=1 \
  -c 'DROP DATABASE IF EXISTS "harmonyhub_test";' \
  -c 'CREATE DATABASE "harmonyhub_test";'

docker compose build api
docker compose run --rm --no-deps \
  -e DATABASE_URL=postgresql+psycopg2://harmonyhub:harmonyhub_dev@db:5432/harmonyhub_test \
  -e HH_TEST_POSTGRES_DATABASE_URL=postgresql+psycopg2://harmonyhub:harmonyhub_dev@db:5432/harmonyhub_test \
  -e HH_COOKIE_SECURE=false \
  -e HH_BACKUP_NIGHTLY_ENABLED=false \
  -e HH_ROUTE_COVERAGE_FILE=/tmp/route_hits.jsonl \
  -v "$PWD/apps/api:/workspace" \
  api sh -lc "pytest -q && python /workspace/scripts/generate_route_coverage_report.py --hits-file /tmp/route_hits.jsonl --output-json /workspace/coverage/api-route-coverage.json --output-md /workspace/coverage/api-route-coverage.md"
```

Generated artifacts are written to:

- `apps/api/coverage/api-route-coverage.json`
- `apps/api/coverage/api-route-coverage.md`

## Configuration

No `.env` file is required or shipped in the repo. For local overrides, pass environment variables through
your shell, Docker Compose overrides, or one-shot command prefixes.

Important env vars:

- `DATABASE_URL`
- `HH_JWT_SECRET`
- `HH_DATA_ENCRYPTION_KEY`
- `HH_PICKUP_CODE_TTL_SECONDS`
- `HH_RATE_LIMIT_USER_PER_MIN`
- `HH_RATE_LIMIT_IP_PER_MIN`
- `HH_TRUSTED_PROXY_CIDRS`
- `HH_COOKIE_SECURE`
- `HH_BOOTSTRAP_ADMIN_USERNAME`
- `HH_BOOTSTRAP_ADMIN_PASSWORD`
- `HH_DEMO_SEED_ON_STARTUP`
- `HH_EXPORT_DIR`
- `HH_BACKUP_DIR`
- `HH_BACKUP_OFFLINE_MEDIUM_DIR`
- `HH_BACKUP_NIGHTLY_ENABLED`
- `HH_BACKUP_NIGHTLY_HOUR_UTC`
- `HH_AUDIT_RETENTION_DAYS`
- `HH_RECOVERY_DRILL_INTERVAL_DAYS`
- `HH_OFFLINE_BACKUP_MEDIUM_PATH`
- `HH_WORKER_OPERATIONS_CHECK_SECONDS`
- `HH_CERT_CN`

## Current scope boundaries

Implemented now:

- runtime/security baseline
- auth + tenancy context + RBAC/ABAC foundation
- API rate limiting (60/min per authenticated user, 300/min per device IP)
- encryption at rest for sensitive persisted fields (TOTP secret, contact/address fields, uploaded raw bytes)
- ABAC dimensional enforcement with department/grade/class-aware row and field scoping on menu/directory surfaces
- directory + repertoire module (data model, APIs, frontend surfaces)
- recommendations + pairing-controls module
- ordering + scheduling module
- fulfillment + handoff module
- imports + merge/account-controls module
- offline sync + conflict UX module
- operations accountability module

Not implemented yet:

- generalized offline queue coverage for mutation surfaces beyond ordering/address-book scope

## Offline boundaries (implemented now)

Queue-enabled now (v1):

- address create/update/delete
- order draft create/update
- order finalize/confirm (queued when offline or transiently disconnected; reconciled later against authoritative server state)

Online-only (explicit):

- login/logout/session auth flows
- ABAC policy and permission-management surfaces
- imports/account-control privileged actions
- scheduling/fulfillment privileged actions
- order quote (requires immediate authoritative capacity response)
- cancellation and other security-sensitive actions
