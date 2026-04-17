# HarmonyHub Static Audit Report

## 1. Verdict
- Overall conclusion: **Fail**

## 2. Scope and Static Verification Boundary
- Reviewed: root documentation/config, FastAPI entry points and route registration, auth/authz layers, core persistence models, ordering/fulfillment/imports/operations/recommendations flows, representative Vue views/router/offline code, API/Vitest test suites, and the generated API route coverage artifact (`README.md:19`, `apps/api/app/main.py:70`, `apps/api/app/api/router.py:19`, `apps/web/src/router/index.ts:15`, `apps/api/coverage/api-route-coverage.md:1`).
- Not reviewed: anything outside the current project directory, including the README reference to `../docs/` (`README.md:33`).
- Intentionally not executed: app runtime, Docker, tests, browser flows, external services, PostgreSQL restore path, and HTTPS startup.
- Manual verification required: real offline behavior in a browser, HTTPS/self-signed proxy startup, compose wiring, worker scheduling cadence, nightly backup timing, and PostgreSQL recovery-drill runtime behavior.

## 3. Repository / Requirement Mapping Summary
- Prompt core goal: a multi-tenant performing arts + concessions portal with four roles, scoped directory/repertoire discovery, recommendation controls, meal ordering/slot capacity/ETA/handoff, CSV imports/merge/account controls, tenant isolation, RBAC/ABAC, offline-ready UX, HTTPS, audit/export/backup/recovery, and encryption-at-rest.
- Main implementation areas mapped: FastAPI auth/context/security, scoped directory/repertoire routes, recommendations/pairing controls, ordering/scheduling/fulfillment APIs, imports/account controls, operations APIs, SQLAlchemy models/migrations, Vue role-based views/offline cache/queue code, and API/Vitest tests.
- Main outcome: the delivery is broadly aligned and substantially complete, but the security/storage implementation does not fully satisfy the prompt because sensitive data is still persisted in plaintext in backup/export artifacts and import normalization JSON records.

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: **Pass**
- Rationale: The repo has clear startup, configuration, test, and structure guidance, and the documented app layout matches the actual `apps/api`, `apps/web`, and `infra/proxy` structure.
- Evidence: `README.md:19`, `README.md:144`, `README.md:169`, `README.md:225`, `run_tests.sh:1`, `apps/api/app/main.py:218`, `apps/web/package.json:6`
- Manual verification note: Runtime instructions are present but were not executed in this audit.

#### 1.2 Material deviation from the Prompt
- Conclusion: **Partial Pass**
- Rationale: The implementation is centered on the prompt and covers the requested business areas, but the security/storage model materially underdelivers on the prompt's encryption-at-rest requirement and only partially reflects the requested flexible JSONB profile/tag/signal architecture.
- Evidence: `README.md:35`, `apps/api/app/db/models.py:156`, `apps/api/app/db/models.py:292`, `apps/api/app/imports/pipeline.py:189`, `apps/api/app/operations/exports.py:157`, `apps/api/app/operations/backups.py:443`

### 2. Delivery Completeness

#### 2.1 Core requirements coverage
- Conclusion: **Partial Pass**
- Rationale: Core role flows, scoped search, masked contact reveal, recommendations, ordering/slot capacity/ETA, pickup-code handoff, imports/merge/freeze, ABAC, rate limiting, auditing, exports, backups, and offline read/queue foundations are present; encryption-at-rest is incomplete for operational artifacts and import normalization records.
- Evidence: `README.md:37`, `apps/api/app/api/routes/directory.py:122`, `apps/api/app/api/routes/recommendations.py:344`, `apps/api/app/api/routes/ordering.py:238`, `apps/api/app/api/routes/fulfillment.py:166`, `apps/api/app/api/routes/imports_admin.py:210`, `apps/api/app/api/routes/operations.py:140`, `apps/api/app/imports/pipeline.py:189`, `apps/api/app/operations/exports.py:163`, `apps/api/app/operations/backups.py:443`

#### 2.2 Basic end-to-end deliverable
- Conclusion: **Pass**
- Rationale: This is a real multi-app project with backend, frontend, worker, migrations, tests, and deployment/config assets rather than a single-file demo.
- Evidence: `README.md:19`, `docker-compose.yml:1`, `apps/api/alembic/env.py:1`, `apps/worker/app/main.py:1`, `apps/web/src/router/index.ts:15`

### 3. Engineering and Architecture Quality

#### 3.1 Engineering structure and module decomposition
- Conclusion: **Pass**
- Rationale: The repository is modularized by concern: routes, authz, orders, imports, operations, DB, worker, and Vue views/components/stores are separated cleanly.
- Evidence: `apps/api/app/api/router.py:19`, `apps/api/app/orders/engine.py:1`, `apps/api/app/imports/pipeline.py:1`, `apps/api/app/operations/backups.py:1`, `apps/web/src/router/index.ts:15`

#### 3.2 Maintainability and extensibility
- Conclusion: **Partial Pass**
- Rationale: The code is generally maintainable, but security-sensitive persistence is handled inconsistently: selected ORM fields use encryption decorators while import JSON documents, export files, and backup files remain plaintext.
- Evidence: `apps/api/app/core/field_encryption.py:70`, `apps/api/app/db/models.py:170`, `apps/api/app/db/models.py:540`, `apps/api/app/db/models.py:576`, `apps/api/app/operations/exports.py:163`, `apps/api/app/operations/backups.py:443`

### 4. Engineering Details and Professionalism

#### 4.1 Error handling, logging, validation, API design
- Conclusion: **Partial Pass**
- Rationale: Input validation, structured errors, rate limiting, CSRF/replay protections, and log redaction are solid, but the sensitive-data handling is not consistently carried through to persisted artifacts.
- Evidence: `apps/api/app/main.py:107`, `apps/api/app/api/deps.py:57`, `apps/api/app/core/logging.py:17`, `apps/api/app/schemas/orders.py:32`, `apps/api/app/imports/security.py:62`, `apps/api/app/operations/exports.py:163`, `apps/api/app/operations/backups.py:443`

#### 4.2 Real product/service shape
- Conclusion: **Pass**
- Rationale: The delivery resembles a real product: multiple bounded domains, migrations, worker operations, role-based UI, offline handling, and a substantial automated test suite.
- Evidence: `README.md:35`, `apps/api/tests/test_ordering.py:83`, `apps/api/tests/test_operations_audit_exports_backups.py:147`, `apps/web/src/views/OrderingView.vue:1`, `apps/web/src/views/OperationsView.vue:1`

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal and constraint fit
- Conclusion: **Partial Pass**
- Rationale: The portal clearly targets the requested performing-arts/concessions workflow and role model, but the implementation weakens a named prompt constraint by leaving multiple sensitive persistence paths unencrypted and only partially reflects the requested flexible JSONB profile/tag/signal model.
- Evidence: `README.md:3`, `README.md:80`, `apps/api/app/db/models.py:156`, `apps/api/app/db/models.py:190`, `apps/api/app/db/models.py:292`, `apps/api/app/imports/pipeline.py:189`, `apps/api/app/operations/exports.py:128`, `apps/api/app/operations/backups.py:216`

### 6. Aesthetics

#### 6.1 Visual and interaction quality
- Conclusion: **Pass**
- Rationale: The frontend has distinct sections, consistent spacing/colors, visible status/error/empty states, focus-visible styling coverage, and role-specific views; no obvious static rendering problems were found.
- Evidence: `apps/web/src/views/DirectoryView.vue:243`, `apps/web/src/views/OperationsView.vue:180`, `apps/web/src/views/RosterView.vue:61`, `apps/web/src/__tests__/styles-runtime.spec.ts:8`
- Manual verification note: Real browser rendering and responsive behavior were not executed.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

#### 1. Sensitive operational artifacts are written to disk in plaintext
- Severity: **Blocker**
- Title: Plaintext export and backup artifacts violate encryption-at-rest
- Conclusion: **Fail**
- Evidence: `apps/api/app/operations/exports.py:117`, `apps/api/app/operations/exports.py:163`, `apps/api/app/operations/exports.py:171`, `apps/api/app/operations/backups.py:216`, `apps/api/app/operations/backups.py:443`, `apps/api/app/operations/backups.py:452`
- Impact: Sensitive directory exports and full tenant backup snapshots are persisted as plaintext CSV/JSON files, directly contradicting the prompt's requirement that sensitive fields be encrypted at rest. Backup artifacts also serialize decrypted ORM values, so encrypted DB columns are effectively re-exposed in cleartext artifacts.
- Minimum actionable fix: Encrypt export and backup artifacts before writing them to disk/offline media, or envelope-encrypt their contents with the same managed key material used for field encryption; add integrity metadata around the encrypted payload rather than storing raw plaintext content.
- Minimal verification path: Static test that generates a sensitive export and backup, inspects artifact bytes on disk, and asserts plaintext email/phone/address values are absent.

### High

#### 2. Import normalization persists raw and normalized member data as plaintext JSON
- Severity: **High**
- Title: Import pipeline leaves sensitive raw/normalized rows unencrypted at rest
- Conclusion: **Fail**
- Evidence: `apps/api/app/imports/pipeline.py:96`, `apps/api/app/imports/pipeline.py:189`, `apps/api/app/db/models.py:569`, `apps/api/app/db/models.py:576`, `apps/api/app/db/models.py:577`, `apps/api/alembic/versions/20260330_0013_postgres_jsonb_partitioned_signals.py:20`
- Impact: Imported member CSV data such as email, phone, and address fields is copied into `raw_row_json` and `normalized_json` without encryption. This leaves sensitive import data readable in the database even though adjacent uploaded raw bytes are encrypted.
- Minimum actionable fix: Encrypt sensitive fields inside import JSON documents, move those fields into encrypted columns, or encrypt the full normalized/raw payload blobs instead of storing them as plaintext JSONB.
- Minimal verification path: Static test that uploads member CSV data, normalizes it, and inspects the underlying DB columns to verify plaintext contact values are not present.

### Medium

#### 3. The storage model only partially matches the prompt's flexible JSONB architecture
- Severity: **Medium**
- Title: Prompted flexible profile/tag/signal document model is only partially implemented
- Conclusion: **Partial Pass**
- Evidence: `apps/api/app/db/models.py:156`, `apps/api/app/db/models.py:177`, `apps/api/app/db/models.py:190`, `apps/api/app/db/models.py:292`, `apps/api/app/db/json_types.py:1`, `apps/api/tests/test_storage_architecture.py:27`
- Impact: The delivery uses JSONB for audit/import/operations documents, but there is no flexible profile document model for performers/users, tags are modeled relationally only, and recommendation signals are scalar rows rather than flexible document-backed signal payloads. This weakens prompt fit and future extensibility against the specified storage approach.
- Minimum actionable fix: Add explicit profile/signal document fields or revise the architecture/docs to match the delivered design and explain the deviation.

#### 4. Security tests miss the artifact and JSON persistence paths where the main defects exist
- Severity: **Medium**
- Title: Test coverage overstates security confidence for encryption-at-rest
- Conclusion: **Partial Pass**
- Evidence: `apps/api/tests/test_encryption_at_rest.py:30`, `apps/api/tests/test_encryption_at_rest.py:94`, `apps/api/tests/test_operations_audit_exports_backups.py:77`, `apps/api/tests/test_operations_audit_exports_backups.py:167`, `apps/api/coverage/api-route-coverage.md:3`
- Impact: The suite verifies encrypted ORM fields and route hits, but it never asserts that generated export files, backup files, or import-normalization JSON rows are encrypted. Severe security defects can therefore ship while route coverage still reports 100%.
- Minimum actionable fix: Add dedicated storage-security tests for export artifacts, backup artifacts, and `import_normalized_rows` persistence.

## 6. Security Review Summary
- Authentication entry points: **Pass**. Local username/password login, lockout, optional TOTP MFA, session cookies, and `/auth/me` are implemented and tested (`apps/api/app/api/routes/auth.py:138`, `apps/api/tests/test_security_baseline.py:115`, `apps/api/tests/test_authz_and_mfa.py:28`).
- Route-level authorization: **Pass**. Core routes use `authorize_for_active_context(...)` with RBAC and ABAC checks (`apps/api/app/api/deps.py:216`, `apps/api/app/api/routes/directory.py:131`, `apps/api/app/api/routes/operations.py:105`).
- Object-level authorization: **Pass**. Directory entries, orders, addresses, exports, backups, and recovery drills are scoped by active organization/program/event/store and often by owner/requester (`apps/api/app/api/routes/directory.py:259`, `apps/api/app/orders/engine.py:333`, `apps/api/app/api/routes/operations.py:215`).
- Function-level authorization: **Pass**. Sensitive actions such as contact reveal, scheduling, fulfillment transitions, account freeze/unfreeze, exports, backups, and ABAC policy management are permission-gated (`apps/api/app/api/routes/directory.py:301`, `apps/api/app/api/routes/fulfillment.py:212`, `apps/api/app/api/routes/imports_admin.py:149`, `apps/api/app/api/routes/policies.py:52`).
- Tenant / user isolation: **Pass**. Scope filters are consistently enforced across directory, repertoire, orders, imports, and operations surfaces (`apps/api/app/api/routes/directory.py:65`, `apps/api/app/api/routes/repertoire.py:52`, `apps/api/app/orders/engine.py:319`, `apps/api/app/imports/pipeline.py:26`).
- Admin / internal / debug protection: **Pass**. ABAC admin routes and operations controls are behind administrator/staff permissions; no open debug endpoints were found (`apps/api/app/api/routes/policies.py:57`, `apps/api/app/api/routes/operations.py:184`).
- Overriding security concern: **Fail** for encryption-at-rest completeness because export/backup artifacts and import-normalization JSON data remain plaintext (`apps/api/app/operations/exports.py:163`, `apps/api/app/operations/backups.py:443`, `apps/api/app/imports/pipeline.py:189`).

## 7. Tests and Logging Review
- Unit tests: **Pass**. Vue/Vitest and Python unit-style tests exist for form behavior, offline fallback, recommendation config, styles, logging redaction, and storage typing (`apps/web/src/__tests__/directory-search-form.spec.ts:5`, `apps/web/src/__tests__/repertoire-view.spec.ts:62`, `apps/api/tests/test_logging_hardening.py:6`, `apps/api/tests/test_storage_architecture.py:27`).
- API / integration tests: **Partial Pass**. The API suite is broad and route-complete, but it does not meaningfully cover artifact encryption or plaintext JSON persistence paths (`apps/api/coverage/api-route-coverage.md:3`, `apps/api/tests/test_operations_audit_exports_backups.py:60`, `apps/api/tests/test_encryption_at_rest.py:30`).
- Logging categories / observability: **Pass**. Structured JSON logging, request IDs, rate-limit headers, and audit records are present (`apps/api/app/core/logging.py:35`, `apps/api/app/main.py:84`, `apps/api/app/operations/audit.py:63`).
- Sensitive-data leakage risk in logs / responses: **Partial Pass**. Logs and audit details are redacted, but persisted export/backup artifacts and import JSON rows expose sensitive values at rest (`apps/api/app/core/logging.py:17`, `apps/api/app/operations/audit.py:49`, `apps/api/app/imports/pipeline.py:192`, `apps/api/app/operations/backups.py:443`).

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests and API/integration tests exist for API, worker, and web layers (`run_tests.sh:20`, `run_tests.sh:28`, `run_tests.sh:31`).
- Test frameworks: `pytest` for API/worker and `vitest` for web (`README.md:175`, `apps/web/package.json:10`).
- Test entry points: `./run_tests.sh` and `npm run test:e2e` are documented, though not executed here (`README.md:169`, `README.md:181`).
- API route coverage artifact claims 82/82 routes hit in tests (`apps/api/coverage/api-route-coverage.md:3`).

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Auth login/session/context flow | `apps/api/tests/test_auth_context.py:17` | Verifies login, `/auth/me`, context switch, logout behavior (`apps/api/tests/test_auth_context.py:22`) | sufficient | None found statically | Keep regression coverage as-is |
| CSRF, replay nonce, lockout | `apps/api/tests/test_security_baseline.py:32` | Verifies stale timestamp, nonce reuse, CSRF mismatch, account lockout (`apps/api/tests/test_security_baseline.py:52`) | sufficient | No explicit test for malformed JWT cookie | Add invalid/tampered session-cookie test |
| RBAC/ABAC route enforcement | `apps/api/tests/test_authz_and_mfa.py:19`, `apps/api/tests/test_abac_dimensions_enforcement.py:1` | Verifies 403 on admin policy access and dimension-based ABAC decisions | basically covered | Broad surface coverage exists, but not every negative path is asserted | Add explicit 401/403 coverage for a representative operations/fulfillment mutation |
| Directory masking/reveal/audit | `apps/api/tests/test_directory_repertoire.py:1` | Verifies masked fields by default and reveal audit persistence (`apps/api/coverage/api-route-coverage.md:24`, `apps/api/coverage/api-route-coverage.md:64`) | sufficient | None material found statically | Keep regression coverage as-is |
| Recommendations / pairing controls | `apps/api/tests/test_recommendations.py:1` | Exercises config inheritance, pinning, allowlist/blocklist, scoring, effective config (`apps/api/coverage/api-route-coverage.md:43`) | basically covered | No artifact-security assertions for recommendation exports/backups | Add ops-security tests rather than more route hits |
| Ordering / slot capacity / ETA / conflicts | `apps/api/tests/test_ordering.py:147`, `apps/api/tests/test_fulfillment.py:222` | Verifies fee resolution, capacity 409 with next slots, ETA recalculation, pickup/delivery transitions | sufficient | No concurrency/race test beyond sequential checks | Add concurrent confirm conflict test if runtime audit is later needed |
| Imports / duplicate merge / freeze controls | `apps/api/tests/test_imports_account_controls.py:108`, `apps/api/tests/test_imports_account_controls.py:175`, `apps/api/tests/test_imports_account_controls.py:259` | Verifies normalize/apply, merge/undo, scoped account freeze/unfreeze, upload validation | basically covered | Does not inspect plaintext in `raw_row_json` / `normalized_json` | Add DB-level encryption test for import normalization rows |
| Export / backup / recovery ops | `apps/api/tests/test_operations_audit_exports_backups.py:60`, `apps/api/tests/test_operations_audit_exports_backups.py:147` | Verifies export masking, audit recording, backup generation, drill record, status reporting | insufficient | Tests read artifacts successfully but never assert they are encrypted | Add artifact-byte assertions for export/backup files |
| Offline-ready frontend fallback | `apps/web/src/__tests__/directory-view.spec.ts:63`, `apps/web/src/__tests__/repertoire-view.spec.ts:62`, `apps/web/src/__tests__/order-composer.spec.ts:83` | Verifies cached read fallback and queued conflict UI states | basically covered | No browser/runtime verification of service worker behavior | Add E2E/manual browser verification outside static audit |

### 8.3 Security Coverage Audit
- Authentication: **Covered meaningfully** by login, logout, MFA, lockout, replay, and CSRF tests (`apps/api/tests/test_auth_context.py:17`, `apps/api/tests/test_authz_and_mfa.py:28`, `apps/api/tests/test_security_baseline.py:32`).
- Route authorization: **Covered meaningfully** for representative RBAC/ABAC paths (`apps/api/tests/test_authz_and_mfa.py:19`, `apps/api/tests/test_ordering.py:204`, `apps/api/tests/test_operations_audit_exports_backups.py:44`).
- Object-level authorization: **Basically covered** for addresses, exports, orders, and account controls (`apps/api/tests/test_ordering.py:83`, `apps/api/tests/test_operations_audit_exports_backups.py:127`, `apps/api/tests/test_imports_account_controls.py:318`).
- Tenant / data isolation: **Basically covered** through active-context tests and scoped queries (`apps/api/tests/test_auth_context.py:33`, `apps/api/tests/test_directory_repertoire.py:1`).
- Admin / internal protection: **Covered meaningfully** for ABAC policy admin and operations boundaries (`apps/api/tests/test_authz_and_mfa.py:19`, `apps/api/tests/test_operations_audit_exports_backups.py:44`).
- Major remaining blind spot: **Severe encryption-at-rest defects could remain undetected while tests pass**, because coverage focuses on route hits and selected ORM columns, not file artifacts or plaintext JSON documents (`apps/api/tests/test_encryption_at_rest.py:30`, `apps/api/tests/test_operations_audit_exports_backups.py:167`, `apps/api/coverage/api-route-coverage.md:3`).

### 8.4 Final Coverage Judgment
- **Partial Pass**
- Major risks covered: auth/session security baseline, RBAC/ABAC enforcement, core directory/order/fulfillment/import flows, route-level access control, and substantial UI/offline state handling.
- Major risks not adequately covered: encryption-at-rest for export files, backup files, offline-medium copies, and import normalization JSON records. The current suites could all pass while these severe data-exposure defects remain in production.

## 9. Final Notes
- The delivered project is substantial and mostly aligned with the business prompt.
- The most important audit outcome is not missing functionality; it is incomplete security hardening around how sensitive data is persisted outside the encrypted ORM field layer.
- Because the prompt explicitly requires encryption at rest for sensitive fields, the artifact/JSON plaintext persistence issues are materially blocking for acceptance.
