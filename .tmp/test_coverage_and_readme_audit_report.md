# Combined Audit: Test Coverage + README

## Scope And Method

- Audit mode: static inspection only.
- Code execution performed: none.
- Files inspected: `README.md`, `docker-compose.yml`, `run_tests.sh`, FastAPI route files under `apps/api/app/api/routes/`, API tests under `apps/api/tests/`, selected web Vitest files under `apps/web/src/__tests__/`, selected Playwright files under `apps/web/e2e/`.

## Project Type Detection

- Declared type: `fullstack`.
- Evidence: `README.md:3` states `Project type: fullstack`.

---

## Part 1: Test Coverage & Sufficiency Audit

### Executive Verdict

- Final test coverage verdict: PASS
- Score: 92/100
- Rationale: all statically discoverable backend endpoints appear to be hit by exact `METHOD + PATH` API tests through `fastapi.testclient.TestClient(create_app())` against the real FastAPI app and database-backed execution path. Coverage breadth is strong. The remaining deductions are for uneven negative-path depth, limited explicit observability assertions, and frontend tests relying heavily on mocked service boundaries.

### Classification Rules Applied

- Endpoint coverage counted only when a test hits the exact declared `METHOD + PATH`.
- `TestClient(create_app())` was treated as real HTTP-layer route coverage.
- API tests were classified as `True No-Mock API Test` unless transport/controller/service/provider mocking was visible in the execution path.
- Frontend Vitest files were not counted as backend endpoint coverage because they mock `@/services/api` and related offline helpers.

### Backend Endpoint Inventory Summary

| Area | Endpoint count |
|---|---:|
| Health | 2 |
| Auth | 6 |
| Context | 2 |
| Dashboard | 1 |
| Directory | 3 |
| Repertoire | 2 |
| Ordering/Menu/Addresses/Scheduling/Orders | 19 |
| Fulfillment | 4 |
| Uploads/Imports/Accounts | 13 |
| Operations | 9 |
| Recommendations + Pairing Rules | 13 |
| Policies | 5 |
| Total | 79 |

### API Test Mapping Table

Legend:

- `TNM` = True No-Mock API test
- `Supp E2E` = also exercised by Playwright/API helper evidence

| Endpoint | Route source | Static test evidence | Classification | Mock detection | Covered |
|---|---|---|---|---|---|
| `GET /api/v1/health/live` | `routes/health.py` | `test_health.py` | TNM | none visible | Yes |
| `GET /api/v1/health/ready` | `routes/health.py` | `test_health.py` | TNM | none visible | Yes |
| `POST /api/v1/auth/login` | `routes/auth.py` | `test_auth_context.py`, `test_security_baseline.py`, many others | TNM | none visible | Yes |
| `POST /api/v1/auth/logout` | `routes/auth.py` | `test_auth_context.py`, `test_security_baseline.py` | TNM | none visible | Yes |
| `GET /api/v1/auth/me` | `routes/auth.py` | `test_auth_context.py`, `test_directory_repertoire.py`, `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/auth/mfa/totp/setup` | `routes/auth.py` | `test_authz_and_mfa.py`, `test_encryption_at_rest.py` | TNM | none visible | Yes |
| `POST /api/v1/auth/mfa/totp/verify` | `routes/auth.py` | `test_authz_and_mfa.py` | TNM | none visible | Yes |
| `POST /api/v1/auth/mfa/totp/enable` | `routes/auth.py` | `test_authz_and_mfa.py` | TNM | none visible | Yes |
| `GET /api/v1/contexts/available` | `routes/context.py` | `test_auth_context.py`, `test_directory_repertoire.py`, `test_recommendations.py`, `test_security_baseline.py` | TNM, Supp E2E | none visible | Yes |
| `POST /api/v1/contexts/active` | `routes/context.py` | `test_auth_context.py`, `test_recommendations.py`, `test_imports_account_controls.py`, `test_security_baseline.py` | TNM, Supp E2E | none visible | Yes |
| `GET /api/v1/dashboard/event` | `routes/dashboard.py` | `test_auth_context.py`, `test_authz_and_mfa.py`, `test_rate_limiting.py`, `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/directory/search` | `routes/directory.py` | `test_directory_repertoire.py`, `test_recommendations.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `GET /api/v1/directory/{entry_id}` | `routes/directory.py` | `test_directory_repertoire.py` | TNM | none visible | Yes |
| `POST /api/v1/directory/{entry_id}/reveal-contact` | `routes/directory.py` | `test_directory_repertoire.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `GET /api/v1/repertoire/search` | `routes/repertoire.py` | `test_directory_repertoire.py`, `test_recommendations.py` | TNM | none visible | Yes |
| `GET /api/v1/repertoire/{item_id}` | `routes/repertoire.py` | `test_directory_repertoire.py` | TNM | none visible | Yes |
| `GET /api/v1/menu/items` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py`, `test_abac_dimensions_enforcement.py` | TNM, Supp E2E | none visible | Yes |
| `GET /api/v1/addresses` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `POST /api/v1/addresses` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py`, `test_encryption_at_rest.py` | TNM | none visible | Yes |
| `PUT /api/v1/addresses/{address_id}` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `DELETE /api/v1/addresses/{address_id}` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `GET /api/v1/scheduling/delivery-zones` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `POST /api/v1/scheduling/delivery-zones` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `PUT /api/v1/scheduling/delivery-zones/{zone_id}` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `DELETE /api/v1/scheduling/delivery-zones/{zone_id}` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `GET /api/v1/scheduling/slot-capacities` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `PUT /api/v1/scheduling/slot-capacities` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py` | TNM | none visible | Yes |
| `DELETE /api/v1/scheduling/slot-capacities` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `POST /api/v1/orders/drafts` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `PUT /api/v1/orders/{order_id}/draft` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `GET /api/v1/orders/mine` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `GET /api/v1/orders/{order_id}` | `routes/ordering.py` | `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `POST /api/v1/orders/{order_id}/pickup-code` | `routes/ordering.py` | `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `POST /api/v1/orders/{order_id}/quote` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `POST /api/v1/orders/{order_id}/confirm` | `routes/ordering.py` | `test_ordering.py`, `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `POST /api/v1/orders/{order_id}/cancel` | `routes/ordering.py` | `test_ordering.py` | TNM | none visible | Yes |
| `GET /api/v1/fulfillment/queues/pickup` | `routes/fulfillment.py` | `test_fulfillment.py` | TNM, Supp E2E | none visible | Yes |
| `GET /api/v1/fulfillment/queues/delivery` | `routes/fulfillment.py` | `test_fulfillment.py` | TNM | none visible | Yes |
| `POST /api/v1/fulfillment/orders/{order_id}/transition` | `routes/fulfillment.py` | `test_fulfillment.py` | TNM | none visible | Yes |
| `POST /api/v1/fulfillment/orders/{order_id}/verify-pickup-code` | `routes/fulfillment.py` | `test_fulfillment.py` | TNM | none visible | Yes |
| `POST /api/v1/uploads` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/uploads` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/batches/upload` | `routes/imports_admin.py` | `test_imports_account_controls.py`, `test_encryption_at_rest.py` | TNM | none visible | Yes |
| `GET /api/v1/imports/batches` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/imports/batches/{batch_id}` | `routes/imports_admin.py` | `test_imports_account_controls.py`, `test_encryption_at_rest.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/batches/{batch_id}/normalize` | `routes/imports_admin.py` | `test_imports_account_controls.py`, `test_encryption_at_rest.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/batches/{batch_id}/apply` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/imports/duplicates` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/duplicates/{duplicate_id}/merge` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/duplicates/{duplicate_id}/ignore` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/imports/merges/{merge_action_id}/undo` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/accounts/users` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/accounts/users/{user_id}/freeze` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `POST /api/v1/accounts/users/{user_id}/unfreeze` | `routes/imports_admin.py` | `test_imports_account_controls.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/audit-events` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `POST /api/v1/operations/exports/directory-csv` | `routes/operations.py` | `test_operations_audit_exports_backups.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/exports/runs` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/exports/runs/{export_run_id}/download` | `routes/operations.py` | `test_operations_audit_exports_backups.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `POST /api/v1/operations/backups/run` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/backups/runs` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `POST /api/v1/operations/recovery-drills` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/recovery-drills` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/operations/status` | `routes/operations.py` | `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/recommendations/config` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `GET /api/v1/recommendations/config/effective` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `POST /api/v1/recommendations/config/validate` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `PUT /api/v1/recommendations/config` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `GET /api/v1/recommendations/featured` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `POST /api/v1/recommendations/featured/{target_id}` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `DELETE /api/v1/recommendations/featured/{target_id}` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `GET /api/v1/recommendations/directory` | `routes/recommendations.py` | `test_recommendations.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `GET /api/v1/recommendations/repertoire` | `routes/recommendations.py` | `test_recommendations.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `GET /api/v1/pairing-rules` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `POST /api/v1/pairing-rules/allowlist` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `POST /api/v1/pairing-rules/blocklist` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `DELETE /api/v1/pairing-rules/{rule_id}` | `routes/recommendations.py` | `test_recommendations.py` | TNM | none visible | Yes |
| `GET /api/v1/admin/policies/abac/surfaces` | `routes/policies.py` | `test_authz_and_mfa.py` | TNM | none visible | Yes |
| `PUT /api/v1/admin/policies/abac/surfaces/{surface}` | `routes/policies.py` | `test_authz_and_mfa.py`, `test_abac_dimensions_enforcement.py`, `test_operations_audit_exports_backups.py` | TNM | none visible | Yes |
| `GET /api/v1/admin/policies/abac/rules` | `routes/policies.py` | `test_authz_and_mfa.py` | TNM | none visible | Yes |
| `POST /api/v1/admin/policies/abac/rules` | `routes/policies.py` | `test_authz_and_mfa.py`, `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |
| `DELETE /api/v1/admin/policies/abac/rules/{rule_id}` | `routes/policies.py` | `test_authz_and_mfa.py` | TNM | none visible | Yes |
| `POST /api/v1/admin/policies/simulate` | `routes/policies.py` | `test_abac_dimensions_enforcement.py` | TNM | none visible | Yes |

### API Coverage Summary

| Metric | Value |
|---|---:|
| Total backend endpoints discovered | 79 |
| Endpoints with exact-path API coverage | 79 |
| Endpoints without exact-path API coverage | 0 |
| Exact-path coverage percentage | 100.0% |
| Endpoints covered by `True No-Mock API Test` | 79 |
| Endpoints covered only by mocked HTTP tests | 0 |
| Endpoints covered only by frontend/UI tests | 0 |

### Mock Detection

API-path test suite (`apps/api/tests`):

- Transport-layer mocking: not found.
- Controller/service/provider mocking in endpoint execution path: not found.
- `TestClient(create_app())` fixture in `apps/api/tests/conftest.py:40-43` boots the real FastAPI app.
- DB-backed setup in `apps/api/tests/conftest.py:22-38` creates schema and seeds data against the configured database engine.
- Visible monkeypatch usage exists for environment and time control in `test_startup_seed_and_migrations.py` and `test_rate_limiting.py`; this does not downgrade endpoint tests to mocked-transport tests.

Frontend Vitest suite (`apps/web/src/__tests__`):

- Heavy mocking present.
- Evidence: `directory-view.spec.ts`, `repertoire-view.spec.ts`, `auth-store.spec.ts`, `policy-management-view.spec.ts`, and others mock `@/services/api`, offline cache modules, and composables.
- Result: these tests are valid frontend unit/component tests but do not count as backend endpoint coverage.

### Backend Unit / API Test Analysis

- API test surface is broad and organized by domain: auth/context/security, directory/repertoire, recommendations, ordering, fulfillment, imports/accounts, operations, rate limiting, storage, encryption, and migrations.
- Exact-path route coverage is materially strong.
- Depth is uneven. Some endpoints have both happy-path and denial-path checks, but many are covered by one or two dominant scenarios rather than a full matrix of malformed input, boundary values, and role permutations.
- Security-sensitive routes are better covered than average: login, lockout, MFA, CSRF/replay enforcement, account freeze, rate limiting, ABAC policies, export sensitivity, and pickup-code verification all have visible dedicated tests.
- Non-endpoint backend tests also exist for logging hardening, encryption-at-rest, storage architecture, migrations, and worker jobs.

### Frontend Unit Test Analysis

- Frontend unit/component tests are present and numerous: 30 `apps/web/src/__tests__/*.ts` files.
- Coverage themes include auth store/bootstrap, router permission guards, directory/repertoire views, ordering UI, imports/account controls, operations control panel, sync/cache behavior, and several UI components.
- Quality characteristic: most frontend tests are component/unit tests with mocked API service functions. This is appropriate for UI behavior isolation, but it means these tests provide little direct evidence for real fullstack integration correctness.

### Frontend Unit-Test Mandatory Verdict For This Fullstack Repo

- Verdict: PASS
- Reason: for a fullstack web repo, frontend unit/component tests are expected and present in meaningful quantity and breadth.

### E2E Expectations Analysis

- Playwright suite exists with 5 spec files: `student-flow.spec.ts`, `staff-flow.spec.ts`, `referee-flow.spec.ts`, `admin-flow.spec.ts`, `completion-video.spec.ts`.
- These specs cover major actor flows and some real API-assisted setup via `apps/web/e2e/support/api.ts`.
- Strength: actor-level integrated journeys exist for student, staff, referee, and admin.
- Limitation: E2E is scenario coverage, not endpoint matrix coverage. It does not replace API-path sufficiency and is documented as optional rather than canonical.

### API Observability Check

Observed implementation:

- `X-Request-ID` header is added in `apps/api/app/main.py:92-113`.
- Rate-limit response headers are added in `apps/api/app/main.py:148-195`.
- Normalized error payloads include `request_id` in `apps/api/app/main.py:197-224`.
- Audit query endpoint exists at `GET /api/v1/operations/audit-events`.
- Route-hit instrumentation exists behind `HH_ROUTE_COVERAGE_FILE` in `apps/api/app/main.py:98-112`.

Observed test evidence:

- Rate-limit headers are asserted in `test_rate_limiting.py:29-66`.
- Audit-event retrieval is exercised in `test_operations_audit_exports_backups.py`.
- No explicit API test was found asserting `X-Request-ID` on normal successful responses.

Observability verdict:

- Partial PASS
- Reason: observability primitives are implemented, but explicit assertion depth is incomplete.

### Test Quality And Sufficiency Analysis

Strengths:

- Full backend route inventory appears covered.
- Coverage goes through real app bootstrap.
- No transport/service mocking detected in API endpoint tests.
- Security and operational workflows receive focused test attention.
- Supporting non-endpoint tests improve confidence around encryption, migrations, logging, and worker behavior.

Key gaps:

- Many endpoints do not show exhaustive boundary-value matrices.
- Happy-path dominance remains visible for several CRUD and list endpoints.
- Observability assertions are not as strong as feature assertions.
- Frontend unit tests rely heavily on mocked service calls, so real browser-to-backend integration still depends mainly on a small Playwright suite.
- Playwright exists but is optional and not part of the canonical `./run_tests.sh` gate.

### Confidence And Assumptions

- Confidence in endpoint inventory: High
- Confidence in exact-path API coverage: High
- Confidence in deeper behavioral sufficiency: Medium-High

Assumptions:

- Static review assumes no hidden dependency overrides outside inspected files.
- Dynamic f-string test paths were matched to their corresponding declared route patterns when the pattern was unambiguous.
- Route inventory is limited to currently registered routers in `apps/api/app/api/router.py` and the `/api/v1` prefix in `apps/api/app/main.py:226`.

---

## Part 2: README Quality & Compliance Audit

### Executive Verdict

- README verdict: PASS

### README Under Audit

- File: `repo/README.md`

### Hard Gate Check

| Gate | Result | Evidence |
|---|---|---|
| Clean markdown and readable structure | PASS | Clear heading hierarchy, code fences, tables, and sectioning throughout `README.md:1-341` |
| Project type declared near top | PASS | `README.md:3` declares `Project type: fullstack` |
| Literal `docker-compose up` for backend/fullstack compatibility | PASS | `README.md:170` includes `docker-compose up --build` |
| Access method documented | PASS | `README.md:156-159`, `184-189` |
| Verification method documented | PASS | `README.md:215-245` documents `./run_tests.sh` and optional Playwright |
| Docker-contained expectations documented | PASS | `README.md:162-183` defines Docker Compose runtime contract and services |
| Demo credentials for auth roles or exact no-auth statement | PASS | `README.md:136-150` lists `admin`, `staff`, `referee`, `student` credentials |

### Engineering Quality Assessment

Strengths:

- README is unusually complete for reviewer onboarding.
- Startup, access, test, architecture, actors, capabilities, and boundaries are all documented.
- Canonical runtime command and canonical broad test command are clearly named.
- Role credentials and environment caveats are explicit.
- Optional Playwright workflow is clearly separated from the canonical broad test gate.
- Current scope and offline boundaries are spelled out rather than implied.

### High Priority Issues

- None.

### Medium Priority Issues

- None.

### Low Priority Issues

- The README is very dense. While compliant and readable, reviewer scanning cost is high because capability detail is front-loaded before some operational guidance.

### Hard Gate Failures

- None.

### README Compliance Notes

- Canonical runtime command documented: `README.md:166-168`.
- Legacy compatibility string documented: `README.md:170`.
- Canonical broad test command documented: `README.md:217-219`.
- Access URL and API base documented: `README.md:156-159`, `186-189`.
- Main repo contents documented: `README.md:21-34`.
- Authentication/demo users documented: `README.md:136-150`.
- Standalone reviewer usability: strong.

---

## Final Combined Verdicts

- Test Coverage & Sufficiency Verdict: PASS
- README Verdict: PASS

## Bottom Line

- The repo passes both audits.
- The strongest result is the backend API coverage breadth: static evidence indicates 79 of 79 declared endpoints are hit by exact-path real app tests.
- The main remaining caution is not missing coverage breadth, but not overstating depth: several areas would still benefit from more explicit boundary and observability assertions.
