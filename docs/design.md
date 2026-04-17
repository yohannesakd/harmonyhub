# HarmonyHub Technical Design

Status: implemented runtime baseline + auth/context/authz + directory/repertoire + recommendations/pairing + ordering/scheduling + fulfillment/handoff + imports/account-controls + offline sync/conflict UX + operations accountability  
Last updated: 2026-04-07

---

## 1) Current implementation scope

Implemented vertical slices:

1. Runtime baseline (web/api/worker/db/proxy under Docker Compose)
2. Security/auth baseline (session + CSRF + replay nonce + lockout + optional TOTP MFA)
3. Tenant context and authz baseline (active context switching, RBAC default-deny, ABAC foundation)
4. Directory/repertoire core module:
   - scoped data model
   - search/filter endpoints
   - masked contact serialization by default
   - explicit reveal endpoint with permission checks and persisted audit events
   - Vue directory and repertoire pages exercising real backend contracts

5. Recommendations + pairing-controls core module:
   - recommendation scoring for directory/repertoire surfaces
   - scope-aware recommendation configuration with inheritance/override
   - featured pin management
    - pairing allowlist/blocklist management with blocklist precedence
    - Vue recommendation rails + management surface

6. Ordering + scheduling core module:
   - context-scoped menu catalog
   - user-owned address book per organization
   - ZIP-based delivery zones and flat fees managed by staff/admin
   - 15-minute slot capacity table managed by staff/admin
   - draft -> quote -> confirm/cancel order lifecycle (no fulfillment in this slice)
   - server-authoritative capacity checks at quote and confirm
   - conflict state and next-slot suggestion behavior
   - ETA calculation from confirmed queue/backlog/recent volume
   - Vue ordering flow + scheduling management surfaces

7. Fulfillment + handoff core module:
   - operator queue APIs and UI surfaces for pickup and delivery
   - service-aware post-confirmation transitions:
     - pickup: `confirmed -> preparing -> ready_for_pickup -> handed_off`
     - delivery: `confirmed -> preparing -> ready_for_dispatch -> out_for_delivery -> delivered`
   - transition validation with role/context enforcement
   - rotating six-digit pickup code issuance for pickup customers
   - staff pickup-code verification endpoint for handoff
   - queue-driven ETA recalculation on confirm/cancel/fulfillment transitions
   - fulfillment action audit-event persistence

8. Imports + account-controls core module:
   - secure upload validation (extension + MIME + magic-byte, 25 MB cap, SHA-256)
   - import-batch pipeline with raw-row preservation + normalize/apply phases
   - raw-row and normalized import JSON persisted as encrypted envelopes inside flexible document columns
   - duplicate candidate queue for member imports with merge/ignore decisions
   - merge undo with safe-undo guard when merged fields were subsequently edited
   - membership-scoped freeze/unfreeze actions with reason tracking, audit persistence, and active-context membership scoping

9. Offline sync + conflict UX module:
   - service-worker powered shell/read caching for non-sensitive ordering reads
   - cached-session fallback for offline bootstrap continuity
   - persisted queued writes for address-book CRUD, order draft create/update, and order finalize/confirm reconciliation
   - sensitive queued payloads are encrypted at rest in browser storage prior to persistence
   - conflict queue state with explicit user review + retry/discard controls

10. Operations accountability module:
    - `operations` API surface for audit queries, exports, backups, recovery-drill records, and status summaries
    - export runs persisted with checksum, row count, requester scope, and encrypted-at-rest artifact path
    - backup runs persisted with checksum, restore-capable tenant logical artifact metadata, encrypted-at-rest artifact storage, and optional offline-medium copy validation
    - recovery drills execute isolated restore verification from backup artifacts (PostgreSQL schema restore path in runtime, SQLite fallback in local/test) and persist scenario/status/evidence metadata
    - 12-month audit retention enforcement via startup + worker compliance prune paths
    - quarterly recovery-drill compliance evaluation (`current|overdue`) in operations status payloads
    - startup nightly backup gate (`HH_BACKUP_NIGHTLY_*`) to ensure one completed nightly run per scope/day
    - operator-facing Vue operations page with filtered audit timeline + export/backup/drill controls

---

## 2) Architecture boundaries

### 2.1 Runtime topology

- `web`: Vue 3 + Pinia + Vue Router + Vite
- `api`: FastAPI + SQLAlchemy + Alembic
- `worker`: recurring heartbeat, offline-medium probe, and operations-compliance checks
- `db`: PostgreSQL
- `proxy`: nginx TLS ingress

### 2.2 API module boundaries

- `auth`: login/logout/me + TOTP endpoints
- `context`: list/switch active context
- `dashboard`: context-scoped dashboard payload
- `directory`: search/detail/reveal contact
- `repertoire`: search/detail
- `recommendations`: recommendations, config, featured pins
- `pairing-rules`: allowlist/blocklist governance
- `menu`: context-scoped concession catalog
- `addresses`: user-owned address-book CRUD
- `scheduling`: delivery zones + slot capacities
- `orders`: draft/quote/confirm/cancel lifecycle
- `fulfillment`: operator queues, transitions, pickup-code verification
- `uploads`: protected file upload intake for import pipeline
- `imports`: batch upload/list/detail/normalize/apply and duplicate merge workflows
- `accounts`: account status list + freeze/unfreeze controls
- `operations`: audit queries + export runs + backup runs + recovery drills + operations status
- `policies`: ABAC surface/rule management + simulation
- shared dependencies (`app/api/deps.py`):
  - session principal resolution
  - replay + CSRF checks
  - active membership resolution
  - reusable RBAC+ABAC authorization dependency

### 2.3 Frontend boundaries

- `services/api.ts`: typed API client and error adapter
- stores:
  - `auth`: session bootstrap/login/logout/permissions
  - `context`: context list + switch
- pages:
  - `DashboardView`
  - `DirectoryView`
  - `RepertoireView`
- `RecommendationsView`
- `ImportsAdminView`
- feature components:
  - directory search form + result cards
  - repertoire search form + result cards
- recommendation rails, config editor, pairing manager
- ordering components:
  - address manager
  - order composer
  - delivery zone manager
  - slot capacity manager
- fulfillment components:
  - pickup queue panel
  - delivery queue panel
  - verification and transition controls
- imports/account-control components:
  - import batch manager
  - duplicate review panel
  - account freeze/unfreeze panel
- operations components:
  - operations control panel with status, export, backup, drill, and audit sections
- offline/sync components and modules:
  - sync status badge with queue/conflict state
  - queued-write persistence and retry orchestration for ordering/address surfaces
  - ordering-page conflict review queue UI

---

## 3) Data model (implemented subset)

### 3.1 Existing foundation tables

- `organizations`, `programs`, `events`, `stores`
- `users`, `memberships`
- `replay_nonces`
- `abac_surface_settings`, `abac_rules`

### 3.2 Directory/repertoire tables

- `directory_entries`
- `repertoire_items`
- `tags`
- `directory_entry_tags`
- `repertoire_item_tags`
- `directory_entry_repertoire_items`
- `availability_windows`
- `audit_events` (used for auth/policy/import/fulfillment/account/export/backup/recovery actions)

### 3.3 Recommendation and pairing tables

- `recommendation_configs`
- `recommendation_signals`
- `recommendation_featured_pins`
- `pairing_rules`

### 3.4 Ordering and scheduling tables

- `menu_items`
- `address_book_entries`
- `delivery_zones`
- `slot_capacities`
- `orders`
- `order_items`

### 3.5 Fulfillment/handoff order fields

`orders` now includes fulfillment lifecycle columns:

- `preparing_at`, `ready_at`, `dispatched_at`, `handed_off_at`, `delivered_at`
- pickup-code lifecycle columns:
  - `pickup_code_hash` (hashed only)
  - `pickup_code_expires_at`
  - `pickup_code_rotated_at`

### 3.6 Tenant/context scoping model

Directory and repertoire records carry explicit scope keys:

- `organization_id`
- `program_id`
- `event_id`
- `store_id`

Search/detail queries are constrained to the active membership scope.

### 3.7 Imports/account-control tables and fields

- `memberships`: `is_frozen`, `frozen_at`, `freeze_reason`, `frozen_by_user_id`, `unfrozen_at`, `unfrozen_by_user_id`
- `uploaded_assets`
- `import_batches`
- `import_normalized_rows`
- `import_duplicate_candidates`
- `import_merge_actions`

### 3.8 Offline persisted client-state model

Client-side persisted stores (localStorage + service-worker cache):

- cached `auth/me` payload for offline bootstrap continuity
  - encrypted-at-rest in browser cache using session-derived key material
- context-scoped directory/repertoire search snapshots keyed by active filter set
- context-scoped ordering snapshots:
  - menu
  - scheduling lists used by staff views
- persisted queued mutations with per-item sync status and conflict payloads:
  - `address.create`, `address.update`, `address.delete`
  - `order.draft.save`, `order.confirm`
- sensitive queued payload classes (`address.create`, `address.update`, `order.draft.save`) are encrypted at rest
- local->server ID mapping remains for migration compatibility and older client artifact cleanup

### 3.9 Operations accountability tables

- `export_runs`
- `backup_runs`
- `recovery_drill_runs`

### 3.10 PostgreSQL JSON document strategy and high-volume recommendation signal shape

- Flexible document columns are defined via a dialect-aware SQLAlchemy type:
  - PostgreSQL: `JSONB`
  - SQLite compatibility (local/test): JSON
- Current flexible document columns include:
  - `audit_events.details_json`
  - `import_batches.validation_issues_json`
  - `import_normalized_rows.raw_row_json`, `normalized_json`, `issues_json`
  - `import_merge_actions.before_snapshot_json`, `applied_changes_json`
  - `export_runs.filters_json`
  - `backup_runs.verification_json`
  - `recovery_drill_runs.evidence_json`
- Sensitive import payloads inside `import_normalized_rows.raw_row_json` and `normalized_json` are wrapped as encrypted JSON envelopes before persistence.
- `recommendation_signals` is the explicit high-volume recommendation event table for storage/index strategy:
  - PostgreSQL range partitioning by `occurred_at`
  - optional `user_id` dimension retained for user-centric signal slicing
  - explicit indexes aligned to dominant filters:
    - scope+surface+time
    - repertoire+time
    - directory+time
    - user+time

---

## 4) Authorization design

### 4.1 RBAC permissions implemented

- `auth.me.read`
- `auth.mfa.manage`
- `context.list`
- `context.switch`
- `dashboard.view`
- `directory.view`
- `directory.contact.reveal`
- `repertoire.view`
- `recommendations.view`
- `recommendations.manage`
- `menu.view`
- `address_book.manage_own`
- `order.manage_own`
- `scheduling.manage`
- `fulfillment.manage`
- `imports.manage`
- `account_control.manage`
- `audit.view`
- `export.manage`
- `backup.manage`
- `recovery_drill.manage`
- `operations.view`
- `abac.policy.manage`

Role defaults:

- `student`, `referee`: view directory/repertoire/recommendations, cannot reveal contact or manage recommendations
- `staff`, `administrator`: view + reveal directory contact + manage recommendations in active scope
- `student`, `referee`: can manage own addresses/orders and view menu in active scope
- `staff`, `administrator`: same as student/referee plus scheduling + fulfillment management
- `staff`, `administrator`: can also manage imports and account freeze/unfreeze in active context
- `staff`, `administrator`: can access operations read/manage controls in active context
- `administrator`: ABAC policy management

Offline boundary rules in implementation:

- queue-enabled: address-book writes, order draft writes, order finalize/confirm
- online-only: auth lifecycle, policy/permission changes, privileged admin actions, quote/cancel and other security-sensitive flows
- server remains source of truth for capacity/security/policy decisions; queued contested actions can become explicit conflicts

### 4.2 ABAC behavior in current implementation

When a surface is enabled:

1. rules are evaluated by ascending priority
2. first match decides allow/deny
3. if no rule matches on enforced surface -> deny

Directory and repertoire route dependencies are ABAC-ready and pass explicit `surface/action` values.

---

## 5) Directory and repertoire behavior

### 5.1 Directory search filters

`GET /directory/search` supports:

- actor/person
- repertoire linkage
- tags
- region
- availability window overlap
- optional generic keyword `q`

### 5.2 Repertoire search filters

`GET /repertoire/search` supports:

- title/composer text (`q` / `repertoire`)
- actor/person linkage
- tags
- linked performer region
- linked performer availability overlap

### 5.3 Masking and reveal flow

- Directory search/detail always return masked contact by default.
- Reveal endpoint (`POST /directory/{entry_id}/reveal-contact`) enforces explicit permission.
- On successful reveal, unmasked contact is returned and an audit event is written.

---

## 6) Recommendation and pairing behavior

### 6.1 Scoring inputs and modes

Recommendation scoring is real and testable for both directory and repertoire surfaces.

Inputs:

- popularity over last 30 days (`recommendation_signals` window)
- recent activity over last 72 hours (`recommendation_signals` window)
- tag matching (request tags overlap with candidate tags)

Modes can be enabled/disabled individually and weighted by configurable weights.

### 6.2 Scope inheritance and override

Config hierarchy:

1. organization default
2. program override
3. event/store override

Effective config resolves nearest existing scope.

Role boundary:

- admin can manage organization/program/event-store configs
- staff can manage event/store config only when delegated by org/program setting `allow_staff_event_store_manage`

### 6.3 Featured pins

- Pins are scoped to active org/program/event/store and surface.
- Recommendation outputs apply pin precedence first, then score ordering.
- Pin limits and optional TTL behavior come from effective config.

### 6.4 Pairing governance

- Pairing rules are managed as allowlist/blocklist per performer↔repertoire pair.
- Restriction evaluation order is explicit: **blocklist overrides allowlist**.
- When pairing enforcement is enabled, recommendation outputs respect these rules.
- Pinned items still pass through pairing restrictions.

---

## 7) Seed and realism strategy

Seed data is additive/idempotent and now includes:

- multiple contexts across organizations/programs/events/stores
- multiple roles/users
- repertoire items with linked performers
- tags and regions across contexts
- multiple availability windows
- recommendation signals across time windows (30d / 72h overlap)
- recommendation scope configs for organization/program delegation behavior
- sample featured pins and sample pairing allowlist
- scoped menu items, ZIP delivery zones, and starter slot capacities per seeded context

This enables deterministic tests for filtering, scope isolation, masking, and reveal auditing.

---

## 8) Verification coverage (current)

Automated tests include:

- auth/context/security baseline
- RBAC/ABAC and MFA behavior
- directory/repertoire filter behavior
- availability overlap behavior
- masked default serialization
- reveal allow/deny behavior by role
- reveal audit event persistence
- recommendation score weighting behavior
- recommendation config inheritance/override and staff delegation boundary
- featured pin ordering
- pairing blocklist overriding allowlist
- recommendation outputs preserving masked contact safety
- user-owned address CRUD behavior and ownership boundaries
- pickup zero-fee behavior and delivery ZIP fee resolution
- delivery out-of-zone validation
- slot capacity conflict on finalize with next-slot suggestions
- scheduling endpoint permission boundary (`scheduling.manage`)
- ETA recalculation with increasing confirmed queue depth
- fulfillment transition enforcement by service type
- pickup-code invalid/expired/valid verification outcomes
- delivery dispatch and completion flow
- ETA recalculation after queue transition events
- fulfillment audit-event persistence checks
- upload rejection paths (extension, MIME, magic bytes, and oversized payload)
- import normalize/apply outcomes for member and roster CSVs
- duplicate merge and safe undo behavior
- account freeze/unfreeze enforcement and audit persistence
- operations API behavior (export/backup/drill/status/audit query)
- audit retention prune behavior for events older than 365-day policy
- quarterly recovery-drill compliance status (`current|overdue`) and overdue-day calculation
- auth login success/failure audit coverage
- ABAC policy-change audit persistence
- queued-write persistence across restart
- reconnect retry processing
- queued contested-action conflict persistence and surfacing
- no pre-commit success representation for queued writes
- sign-out/account-switch cleanup of per-user read-cache + queued payload artifacts
- frontend component behavior for new directory/repertoire surfaces
- frontend recommendation config and pinning interaction components
- frontend ordering/scheduling component interactions
- frontend imports/account-control component interactions
- frontend offline queue component/store behavior

Canonical verification path remains `./run_tests.sh` plus Docker startup checks.

Database setup for delivery packaging is standardized through `repo/init_db.sh`, which creates the app/test databases through Docker Compose and applies Alembic migrations without requiring host Python tooling.

---

## 9) Known deferred areas

- broader queue coverage beyond ordering/address-book surface set
