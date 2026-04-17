# HarmonyHub API Specification (Implemented)

Status: reflects implemented backend routes  
Last updated: 2026-04-07

Base path: `/api/v1`

---

## 1) Shared conventions

### 1.1 Auth + transport

- HTTPS through proxy in canonical runtime
- Session cookie auth (`hh_session`)
- CSRF cookie/header pair (`hh_csrf` + `X-CSRF-Token`) for protected mutations

### 1.2 Replay protection

Protected mutating routes require:

- `X-Request-Nonce`
- `X-Request-Timestamp` (ISO/RFC3339; ±5-minute window)

On failure: `409 REPLAY_REJECTED`

### 1.3 Rate limiting

- API routes under `/api/v1` are rate limited (health probes excluded):
  - `60 requests/minute` per authenticated user
  - `300 requests/minute` per device IP
- Auth entry points (including `/auth/login`) are covered by IP limiting.
- Effective client IP derivation for limiter:
  - forwarded chain headers are trusted only when the immediate peer IP is inside `HH_TRUSTED_PROXY_CIDRS`
  - when trusted proxy forwarding is enabled, limiter uses the last untrusted `X-Forwarded-For` hop
  - otherwise limiter uses direct request peer IP and ignores forwarded headers
- Exceeded requests return `429 RATE_LIMIT_EXCEEDED` with:
  - `Retry-After`
  - rate-limit metadata headers
  - error details (`scope`, `limit`, `window_seconds`, `retry_after_seconds`, `reset_at`)

### 1.4 Error envelope

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable summary",
    "details": {},
    "request_id": "uuid"
  }
}
```

### 1.5 Encryption at rest for sensitive persisted fields

The API stores the following high-risk fields encrypted at rest:

- `users.mfa_totp_secret`
- `directory_entries.email`, `directory_entries.phone`, `directory_entries.address_line1`
- `address_book_entries.recipient_name`, `line1`, `line2`, `phone`
- `uploaded_assets.raw_bytes`
- `import_normalized_rows.raw_row_json` and `normalized_json` via encrypted JSON envelope payloads

Operational artifacts are also encrypted at rest on disk before persistence:

- directory export CSV artifacts
- tenant backup artifacts and offline-copy artifacts

Encryption is transparent to API consumers (request/response payloads are unchanged).

### 1.6 PostgreSQL document + recommendation-signal storage shape

- Flexible document fields are dialect-aware:
  - PostgreSQL canonical runtime uses `JSONB`
  - SQLite local/test compatibility path uses JSON
- PostgreSQL schema migration strategy explicitly applies range partitioning for the high-volume `recommendation_signals` table by `occurred_at`.
- Recommendation-signal indexing is explicitly aligned to prompt-required dimensions:
  - `repertoire_item_id + occurred_at`
  - `user_id + occurred_at`
  - plus scoped `organization/program/event/store/surface + occurred_at` and `directory_entry_id + occurred_at` paths

---

## 2) Implemented route groups

- `health`
- `auth`
- `context`
- `dashboard`
- `directory`
- `repertoire`
- `recommendations`
- `pairing-rules`
- `menu`
- `addresses`
- `scheduling`
- `orders`
- `fulfillment`
- `uploads`
- `imports`
- `accounts`
- `admin/policies` (ABAC admin)

---

## 3) Health

- `GET /health/live` -> `{"status":"ok"}`
- `GET /health/ready` -> DB readiness check + `{"status":"ready"}`

---

## 4) Auth

### `POST /auth/login`

Body:

```json
{
  "username": "string",
  "password": "string",
  "totp_code": "string | optional"
}
```

Behavior:

- validates credentials
- lockout enforced (`ACCOUNT_LOCKED`, 423)
- if user MFA enabled and no/invalid TOTP provided -> `MFA_REQUIRED` / `MFA_INVALID`
- if all memberships available to the user are frozen, login returns `ACCOUNT_FROZEN` (423)
- otherwise login selects the first unfrozen membership as the active context
- sets session + CSRF cookies
- returns user summary + active context + active-context permissions

### `GET /auth/me`

Returns:

- user summary
- active context
- active-context permissions
- `available_contexts` (unfrozen memberships only)

### `POST /auth/logout`

Requires session + CSRF + replay headers. Clears auth cookies.

### TOTP endpoints (`POST`)

All require session + CSRF + replay headers:

- `/auth/mfa/totp/setup`
- `/auth/mfa/totp/verify`
- `/auth/mfa/totp/enable`

---

## 5) Context + dashboard

### `GET /contexts/available`

Returns context memberships user can list.

### `POST /contexts/active`

Body:

```json
{
  "organization_id": "uuid",
  "program_id": "uuid",
  "event_id": "uuid",
  "store_id": "uuid"
}
```

Behavior:

- validates membership for scope
- selecting a frozen membership returns `423 ACCOUNT_FROZEN`
- RBAC check `context.switch`
- ABAC check (`surface=context`, `action=switch`)
- rotates session token with updated active context

### `GET /dashboard/event`

Authorization sequence:

1. active membership from session context
2. RBAC check `dashboard.view`
3. ABAC check (`surface=dashboard`, `action=view`)

Returns context-scoped organization/event/store names + role + permission list.

---

## 6) Directory module

Directory routes require active context and `directory.view` unless noted.

### 6.1 `GET /directory/search`

Query parameters:

- `q`
- `actor`
- `repertoire`
- `tags` (repeatable)
- `region`
- `availability_start` (ISO timestamp)
- `availability_end` (ISO timestamp)

Behavior:

- query is scope-bound to active `organization/program/event/store`
- filters support actor/person, repertoire title/composer linkage, tags, region, and availability overlap
- contact fields are masked by default
- optional ABAC row filtering can be applied with `surface=directory`, `action=search_row`
- optional ABAC field-level suppression can be applied with `surface=directory`, `action=contact_field_view`

Response shape:

```json
{
  "results": [
    {
      "id": "uuid",
      "display_name": "Ava Martinez",
      "stage_name": "Ava M.",
      "region": "North Region",
      "tags": ["jazz"],
      "repertoire": ["Moonlight Sonata"],
      "availability_windows": [
        { "starts_at": "...", "ends_at": "..." }
      ],
      "contact": {
        "email": "a***@harmonyhub.example",
        "phone": "***-***-2233",
        "address_line1": "*** Hidden address ***",
        "masked": true
      },
      "can_reveal_contact": false
    }
  ],
  "total": 1
}
```

### 6.2 `GET /directory/{entry_id}`

Returns detail for scoped entry. Contact fields remain masked by default.

When configured, ABAC row filtering can hide specific entries via `surface=directory`, `action=view_row`.

### 6.3 `POST /directory/{entry_id}/reveal-contact`

Requires:

- session + CSRF + replay headers
- RBAC permission `directory.contact.reveal` (staff/administrator in current matrix)
- ABAC check (`surface=directory`, `action=reveal_contact`)

Behavior:

- returns unmasked contact payload
- persists an audit event (`action=directory.contact.reveal`, target entry + actor metadata)
- optional ABAC row/field checks still apply (`reveal_row`, `contact_field_view`)

---

## 7) Repertoire module

Repertoire routes require active context + `repertoire.view`.

### 7.1 `GET /repertoire/search`

Query parameters:

- `q`
- `repertoire`
- `actor`
- `tags` (repeatable)
- `region`
- `availability_start`
- `availability_end`

Behavior:

- active context scope enforced on repertoire items and linked performer rows
- supports filtering by title/composer, linked actor, tags, linked performer region, and linked availability overlap

Returns:

```json
{
  "results": [
    {
      "id": "uuid",
      "title": "Moonlight Sonata",
      "composer": "L. van Beethoven",
      "tags": ["classical", "featured"],
      "performer_names": ["Ava Martinez", "Chloe Ng"],
      "regions": ["North Region"]
    }
  ],
  "total": 1
}
```

### 7.2 `GET /repertoire/{item_id}`

Returns scoped repertoire detail with performer list and performer count.

---

## 8) Recommendations module

Recommendation routes require active context + `recommendations.view`.

### 8.1 `GET /recommendations/directory`

Query params:

- `tags` (repeatable, optional)
- `repertoire_item_id` (optional; enables pair restriction checks)
- `limit`

Behavior:

- candidates are scoped to active context
- score uses three inputs:
  - popularity over 30 days
  - recent activity over 72 hours
  - tag match overlap
- effective scope config controls enabled modes and weights
- output remains contact-masked
- featured pins are ordered first (within configured limits)
- pairing restrictions are enforced when enabled and contextual pair input is provided

### 8.2 `GET /recommendations/repertoire`

Query params:

- `tags` (repeatable, optional)
- `directory_entry_id` (optional; enables pair restriction checks)
- `limit`

Same scoring and config semantics as directory recommendations, but for repertoire items.

### 8.3 Recommendation config APIs

`GET /recommendations/config?scope=organization|program|event_store`

- returns requested-scope config (or inherited/default projection when no exact override exists)

`GET /recommendations/config/effective`

- returns currently effective config for active context

`POST /recommendations/config/validate`

- validates and normalizes weight payload

`PUT /recommendations/config` (CSRF + replay required)

- upserts scope config
- role boundary:
  - admin can manage org/program/event-store scopes
  - staff can manage event-store scope only when delegated by higher scope

### 8.4 Featured pin APIs

- `GET /recommendations/featured?surface=directory|repertoire`
- `POST /recommendations/featured/{target_id}` (CSRF + replay required)
- `DELETE /recommendations/featured/{target_id}?surface=...` (CSRF + replay required)

Pins are context-scoped and surfaced in recommendation ranking.

---

## 9) Pairing rules module

Pairing routes use `/pairing-rules` prefix.

- `GET /pairing-rules`
- `POST /pairing-rules/allowlist` (CSRF + replay required)
- `POST /pairing-rules/blocklist` (CSRF + replay required)
- `DELETE /pairing-rules/{rule_id}` (CSRF + replay required)

Evaluation precedence in recommendation filtering: **blocklist overrides allowlist**.

---

## 10) ABAC policy admin (`/admin/policies`)

All routes require active membership with `abac.policy.manage`.

- `GET /admin/policies/abac/surfaces`
- `PUT /admin/policies/abac/surfaces/{surface}` (CSRF + replay required)
- `GET /admin/policies/abac/rules?surface=...&action=...`
- `POST /admin/policies/abac/rules` (CSRF + replay required)
- `DELETE /admin/policies/abac/rules/{rule_id}` (CSRF + replay required)
- `POST /admin/policies/simulate`

Rule model supports optional dimensional attributes:

- subject: `subject_department`, `subject_grade`, `subject_class`
- resource: `resource_department`, `resource_grade`, `resource_class`
- field selector: `resource_field`

Simulation request supports:

- `subject.{department,grade,class_code}`
- `resource.{department,grade,class_code,field}`

---

## 11) Ordering and scheduling module

All ordering/scheduling routes require active context authorization.

### 11.1 Menu

- `GET /menu/items`
  - permission: `menu.view`
  - returns active menu rows in current org/program/event/store scope
  - optional ABAC row filtering can be applied with `surface=ordering`, `action=menu_row_view`

### 11.2 Address book (user-owned)

- `GET /addresses`
- `POST /addresses` (CSRF + replay required)
- `PUT /addresses/{address_id}` (CSRF + replay required)
- `DELETE /addresses/{address_id}` (CSRF + replay required)

Permission: `address_book.manage_own`

Ownership boundary:

- rows are always constrained to current authenticated user + organization
- cross-user update/delete attempts return not-found/validation envelope

### 11.3 Staff scheduling controls

- `GET /scheduling/delivery-zones`
- `POST /scheduling/delivery-zones` (CSRF + replay required)
- `PUT /scheduling/delivery-zones/{zone_id}` (CSRF + replay required)
- `DELETE /scheduling/delivery-zones/{zone_id}` (CSRF + replay required)
- `GET /scheduling/slot-capacities?for_date=YYYY-MM-DD`
- `PUT /scheduling/slot-capacities` (CSRF + replay required)
- `DELETE /scheduling/slot-capacities?slot_start=<ISO>` (CSRF + replay required)

Permission: `scheduling.manage` (staff/administrator defaults).

### 11.4 Orders

- `POST /orders/drafts` (CSRF + replay required)
- `PUT /orders/{order_id}/draft` (CSRF + replay required)
- `GET /orders/mine`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/quote` (CSRF + replay required)
- `POST /orders/{order_id}/confirm` (CSRF + replay required)
- `POST /orders/{order_id}/cancel` (CSRF + replay required)
- `POST /orders/{order_id}/pickup-code` (CSRF + replay required)

Permission: `order.manage_own`

Behavior highlights:

- `slot_start` must align to 15-minute boundaries.
- pickup:
  - `delivery_fee_cents = 0`
  - no address/zone required
- delivery:
  - requires `address_book_entry_id`
  - ZIP must map to an active `delivery_zone` for active context or request fails with `VALIDATION_ERROR`.
- quote and confirm both re-run server-authoritative capacity checks.
- if requested slot is full, API returns `409 VALIDATION_ERROR` with `details.next_slots` suggestions and order is marked `conflict`.

Quote conflict example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Requested slot is at capacity",
    "details": {
      "order_id": "uuid",
      "next_slots": ["2026-04-01T12:45:00+00:00", "2026-04-01T13:00:00+00:00"]
    }
  }
}
```

Order responses include:

- totals (`subtotal_cents`, `delivery_fee_cents`, `total_cents`)
- computed `eta_minutes`
- state fields (`status`, `quote_expires_at`, `conflict_reason`, `cancel_reason`, `confirmed_at`)
- expanded line items

---

## 12) Fulfillment + handoff module

All fulfillment routes are context-scoped and require `fulfillment.manage`.

### 12.1 Queue endpoints

- `GET /fulfillment/queues/pickup`
- `GET /fulfillment/queues/delivery`

Both return operator-ready queue payloads with line items and delivery-address summaries when applicable.

### 12.2 Transition endpoint

- `POST /fulfillment/orders/{order_id}/transition` (CSRF + replay required)

Body:

```json
{
  "target_status": "preparing|ready_for_pickup|ready_for_dispatch|out_for_delivery|delivered|cancelled",
  "cancel_reason": "optional"
}
```

Service-type-aware validation:

- pickup path: `confirmed -> preparing -> ready_for_pickup -> handed_off`
- delivery path: `confirmed -> preparing -> ready_for_dispatch -> out_for_delivery -> delivered`
- invalid cross-service transitions are rejected with `422 VALIDATION_ERROR`

`handed_off` cannot be set via transition endpoint; it requires pickup-code verification.

### 12.3 Pickup-code verification endpoint

- `POST /fulfillment/orders/{order_id}/verify-pickup-code` (CSRF + replay required)

Body:

```json
{ "code": "123456" }
```

Behavior:

- verifies active hashed 6-digit code (TTL-bound)
- rejects invalid/expired/missing codes with `422 VALIDATION_ERROR`
- on success, transitions order to `handed_off`

### 12.4 Customer pickup-code issuance endpoint

- `POST /orders/{order_id}/pickup-code` (CSRF + replay required)

Behavior:

- available only for own pickup orders in eligible states (`confirmed|preparing|ready_for_pickup`)
- rotates a fresh 6-digit code
- stores only hash + expiry timestamps server-side
- returns plaintext code once in response payload

---

## 13) Uploads/imports/account-controls module

All routes are context-scoped and use RBAC + ABAC dependencies.

### 13.1 Upload intake (`/uploads`)

- `POST /uploads` (multipart; CSRF + replay required)
- `GET /uploads`

Upload validation behavior:

- allowed extensions: `csv`, `pdf`, `jpg`/`jpeg`, `png`
- max file size: 25 MB
- extension + MIME + magic-byte validation
- SHA-256 persisted for accepted uploads
- rejection envelope: `UPLOAD_REJECTED` (`422` or `413` for oversize)

### 13.2 Import batches (`/imports`)

- `POST /imports/batches/upload` (multipart CSV; `kind=member|roster`; CSRF + replay required)
- `GET /imports/batches`
- `GET /imports/batches/{batch_id}`
- `POST /imports/batches/{batch_id}/normalize` (CSRF + replay required)
- `POST /imports/batches/{batch_id}/apply` (CSRF + replay required)

Behavior summary:

- upload bytes and per-row raw CSV payloads are preserved
- normalize computes valid/invalid rows and issue metadata
- member imports surface duplicate candidates for operator review
- apply imports valid non-duplicate (or resolved) rows into scoped directory/repertoire tables

### 13.3 Duplicate review + merge (`/imports`)

- `GET /imports/duplicates?status=open&status=merged...`
- `POST /imports/duplicates/{duplicate_id}/merge` (CSRF + replay required)
- `POST /imports/duplicates/{duplicate_id}/ignore` (CSRF + replay required)
- `POST /imports/merges/{merge_action_id}/undo` (CSRF + replay required)

Undo safety behavior:

- undo is rejected if any field applied by merge no longer matches the merge-applied value (prevents unsafe rollback after later edits)

### 13.4 Account controls (`/accounts`)

- `GET /accounts/users`
- `POST /accounts/users/{user_id}/freeze` (CSRF + replay required)
- `POST /accounts/users/{user_id}/unfreeze` (CSRF + replay required)

Scope behavior:

- account list and freeze/unfreeze targets are restricted to users with membership in the authorized active context scope (`organization_id + program_id + event_id + store_id`)
- out-of-scope account targets return `404 VALIDATION_ERROR`

Freeze behavior:

- freeze/unfreeze state is stored on the scoped `memberships` row, not the global `users` row
- a frozen active context returns `423 ACCOUNT_FROZEN`
- login succeeds if the user still has at least one unfrozen membership and fails with `423 ACCOUNT_FROZEN` only when all memberships are frozen
- freeze/unfreeze actions persist `audit_events` entries with operator reason details

---

## 14) Operations accountability (`/operations`)

### 14.1 Audit query API

- `GET /operations/audit-events`
- permission: `audit.view`
- scoped to active membership context (`organization/program/event/store`)
- query filters:
  - `action_prefix`
  - `actor_user_id`
  - `target_type`
  - `target_id`
  - `start_at`, `end_at`
  - `limit` (1-500)
- response sanitizes secret and contact-bearing keys (`password`, `code`, `token`, `email`, `phone`, `address*`, etc.) to `***REDACTED***`

### 14.2 Directory export APIs

- `POST /operations/exports/directory-csv` (CSRF + replay required)
  - permission: `export.manage`
  - `include_sensitive=true` additionally requires `directory.contact.reveal`
  - export rows remain scoped to active context
  - masked contact values are used when `include_sensitive=false`
  - creates requester-scoped `export_runs` record with plaintext checksum + metadata
  - export artifact bytes are encrypted at rest on disk
  - writes audit event `exports.directory.generated`
- `GET /operations/exports/runs`
- `GET /operations/exports/runs/{export_run_id}/download`
  - scoped by active context and requesting user
  - decrypts artifact bytes only for the authorized download response after checksum verification
  - writes audit event `exports.directory.downloaded`

### 14.3 Backup and recovery APIs

- `POST /operations/backups/run` (CSRF + replay required)
  - permission: `backup.manage`
  - creates restore-capable tenant logical backup artifact JSON from critical scoped tables, computes SHA-256 over plaintext payload, then persists encrypted artifact bytes
  - optional offline-medium copy verification compares encrypted artifact copy bytes while restore/recovery paths decrypt and verify plaintext checksum before load
  - writes audit event `backup.run.completed`
- `GET /operations/backups/runs`
  - permission: `operations.view`
- `POST /operations/recovery-drills` (CSRF + replay required)
  - permission: `recovery_drill.manage`
  - optional scoped `backup_run_id` reference (if omitted and no completed backup exists, API creates `drill_snapshot` backup first)
  - executes real restore workflow and validates restored table counts vs artifact manifest:
    - PostgreSQL runtime restores into an isolated PostgreSQL schema
    - SQLite local/test runtime restores into isolated SQLite target
  - persists `recovery_drill_runs` with restore evidence (`evidence_json.restore`)
  - writes audit event `recovery.drill.recorded`
- `GET /operations/recovery-drills`
  - permission: `operations.view`
- `GET /operations/status`
  - permission: `operations.view`
  - returns current scoped operational counters + latest backup/drill summaries
  - includes `audit_retention`:
    - `retention_days`
    - `cutoff_at`
    - `events_older_than_retention`
  - includes `recovery_drill_compliance`:
    - `interval_days`
    - `status` (`current` or `overdue`)
    - `latest_performed_at`
    - `due_at`
    - `days_until_due`
    - `days_overdue`
  - compliance values are computed against configured policy windows (`HH_AUDIT_RETENTION_DAYS`, `HH_RECOVERY_DRILL_INTERVAL_DAYS`)

---

## 15) Notable error codes in this slice

- `AUTH_REQUIRED` (401)
- `ACCOUNT_FROZEN` (423)
- `ACCOUNT_LOCKED` (423)
- `MFA_REQUIRED` (401)
- `MFA_INVALID` (401)
- `MFA_SETUP_REQUIRED` (400)
- `MFA_SETUP_INVALID` (500)
- `CSRF_INVALID` (403)
- `REPLAY_REJECTED` (409)
- `RATE_LIMIT_EXCEEDED` (429)
- `FORBIDDEN` (403)
- `VALIDATION_ERROR` (422/404 depending route)
- `UPLOAD_REJECTED` (422/413)

---

## 16) Offline sync and reconciliation behavior (frontend contract)

Client behavior implemented on top of existing APIs:

- service worker caches shell/static assets only; user API GET responses are not service-worker cached
- cached `/auth/me` payload is stored with per-user keying and encrypted-at-rest browser envelope to prevent plaintext bootstrap persistence
- cached `/auth/me` bootstrap fallback requires active session key material (`hh_csrf`) for decryption
- cached reads for directory and repertoire searches are keyed by user + active context + filter set and used when network fetches fail
- cached reads for ordering remain limited to menu/scheduling snapshots when network fetches fail
- sign-out and account-switch boundaries clear per-user cached reads and queued payloads
- sensitive queued payloads (address create/update and order draft save) are encrypted in browser storage

Queue-enabled mutation categories in this release:

- address book create/update/delete (`/addresses`)
- order draft create/update (`/orders/drafts`, `/orders/{id}/draft`)
- order finalize/confirm (`/orders/{id}/confirm`) with deferred reconciliation

Conflict handling for contested queued actions:

- queued `confirm` replay can receive server `409 VALIDATION_ERROR` with `details.next_slots`
- client surfaces this as a queue conflict with server message/details and requires explicit user follow-up
- UI does not treat queued actions as committed success until replay is server-committed

Online-only boundaries (not queued in this release):

- auth lifecycle (`/auth/*` mutations)
- ABAC/policy admin changes
- imports/account-control privileged mutations
- scheduling/fulfillment privileged mutations
- quote and cancel operations where immediate authoritative checks are required by policy in this release
