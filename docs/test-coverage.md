# Test Coverage Summary

Last updated: 2026-04-07

## Canonical verification entrypoints

- Runtime: `repo/docker-compose.yml` via `docker compose up --build`
- Database setup: `repo/init_db.sh`
- Full project test gate: `repo/run_tests.sh`
- Browser E2E: `repo/apps/web/package.json` script `npm run test:e2e`

## What is covered

### Backend

- FastAPI endpoint tests run through real application routes with `TestClient`.
- API route inventory artifact shows **82 / 82 routes covered (100.00%)**.
- Route inventory can be regenerated from the packaged repo using the documented API route-coverage commands in `repo/README.md`.

Key covered backend areas:

- auth, session, MFA, CSRF, replay protection, and lockout
- tenant context switching, RBAC, and ABAC enforcement
- directory masking, contact reveal auditing, and cross-surface ABAC consistency
- repertoire and recommendation flows, including runtime-written recommendation signals
- ordering, scheduling, ETA, and capacity conflict handling
- fulfillment queues and pickup-code verification
- imports, duplicate merge/undo, membership-scoped account freeze controls, and encrypted import JSON persistence
- audit, requester-scoped exports, encrypted backup artifacts, and recovery-drill operations
- startup demo-seed opt-in behavior and Alembic migration-path schema checks

Representative backend test locations:

- `repo/apps/api/tests/test_security_baseline.py`
- `repo/apps/api/tests/test_abac_dimensions_enforcement.py`
- `repo/apps/api/tests/test_recommendations.py`
- `repo/apps/api/tests/test_ordering.py`
- `repo/apps/api/tests/test_fulfillment.py`
- `repo/apps/api/tests/test_imports_account_controls.py`
- `repo/apps/api/tests/test_operations_audit_exports_backups.py`
- `repo/apps/api/tests/test_encryption_at_rest.py`
- `repo/apps/api/tests/test_startup_seed_and_migrations.py`

### Frontend unit and component coverage

- Web unit/component suite runs through Vitest from `repo/apps/web`.
- Coverage includes auth bootstrap, router guards, directory/repertoire views, ordering flows, operations controls, policy management, offline storage helpers, and sync queue behavior.

Representative test locations:

- `repo/apps/web/src/__tests__/login-view.spec.ts`
- `repo/apps/web/src/__tests__/directory-view.spec.ts`
- `repo/apps/web/src/__tests__/order-composer.spec.ts`
- `repo/apps/web/src/__tests__/policy-management-view.spec.ts`
- `repo/apps/web/src/__tests__/router-permission-guards.spec.ts`

### Browser end-to-end coverage

- Playwright role flows exist for student, referee, staff, and administrator.
- The packaged repo keeps the Playwright specs; generated browser artifacts are intentionally not part of the final delivery package.

Representative spec locations:

- `repo/apps/web/e2e/student-flow.spec.ts`
- `repo/apps/web/e2e/referee-flow.spec.ts`
- `repo/apps/web/e2e/staff-flow.spec.ts`
- `repo/apps/web/e2e/admin-flow.spec.ts`

## Coverage boundaries and interpretation

- The strongest backend surface metric is the delivered route inventory artifact, which demonstrates full route-surface exercise at the FastAPI application layer.
- Security-sensitive persistence paths now have targeted coverage for encrypted export artifacts, encrypted backup artifacts, and encrypted import-normalization payload storage.
- Startup/bootstrap risk now has explicit test coverage for dev-only demo seeding and a PostgreSQL/Alembic migration-path check.
- The migration-path test is PostgreSQL-gated and skips when `HH_TEST_POSTGRES_DATABASE_URL` is unavailable; `repo/run_tests.sh` provides that variable in the canonical Dockerized path.
- Browser rendering quality, live service-worker behavior, and HTTPS proxy behavior still require runtime verification and are not proven by static test evidence alone.

## Reviewer guidance

For a reviewer validating the delivered project:

1. Run `./init_db.sh` from `repo/`.
2. Run `docker compose up --build` from `repo/`.
3. Run `./run_tests.sh` from `repo/`.
4. Run `npm run test:e2e` from `repo/apps/web` if fresh browser verification is desired.
5. Optionally regenerate the API route coverage inventory using the commands documented in `repo/README.md` if exact per-route evidence is needed.
