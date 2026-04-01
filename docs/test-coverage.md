# Test Coverage Summary

## Canonical verification entrypoints

- Runtime: `repo/docker-compose.yml` via `docker compose up --build`
- Full project test gate: `repo/run_tests.sh`
- Browser E2E: `repo/apps/web/package.json` script `npm run test:e2e`

## What is covered

### Backend

- FastAPI endpoint tests run through real application routes with `TestClient`.
- API route inventory artifact shows **82 / 82 routes covered (100.00%)**.
- Coverage artifact: `repo/apps/api/coverage/api-route-coverage.md`

Key covered backend areas:

- auth, session, MFA, CSRF, replay protection, and lockout
- tenant context switching, RBAC, and ABAC enforcement
- directory masking and contact reveal auditing
- repertoire and recommendation flows
- ordering, scheduling, ETA, and capacity conflict handling
- fulfillment queues and pickup-code verification
- imports, duplicate merge/undo, and account freeze controls
- audit, export, backup, and recovery-drill operations

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
- Delivered browser evidence lives under `repo/apps/web/e2e-artifacts/`.

Representative proof files:

- Student masked directory and offline queue:
  - `repo/apps/web/e2e-artifacts/screenshots/student/1774789032846-directory-masked.png`
  - `repo/apps/web/e2e-artifacts/screenshots/student/1774789035145-offline-queue.png`
- Referee limited-access ordering:
  - `repo/apps/web/e2e-artifacts/screenshots/referee/1774789026958-ordering-confirmed.png`
- Staff fulfillment and admin operations:
  - `repo/apps/web/e2e-artifacts/screenshots/staff/1774789031551-fulfillment-verified-handoff.png`
  - `repo/apps/web/e2e-artifacts/screenshots/admin/1774789013722-operations-controls.png`

## Coverage boundaries and interpretation

- The strongest backend surface metric is the delivered route inventory artifact, which demonstrates full route-surface exercise at the FastAPI application layer.
- The browser evidence demonstrates real product flows across the main user roles rather than mock-only UI checks.
- `repo/run_tests.sh` is the required all-project gate because it validates API, worker, and web suites together against the canonical Docker/PostgreSQL path.

## Reviewer guidance

For a reviewer validating the delivered project:

1. Run `docker compose up --build` from `repo/`.
2. Run `./run_tests.sh` from `repo/`.
3. Run `npm run test:e2e` from `repo/apps/web` if fresh browser evidence is desired.
4. Review `repo/apps/api/coverage/api-route-coverage.md` for exact backend route coverage.
