# HarmonyHub clarification notes

## Principle used for clarification
Where the prompt left implementation room, defaults below were chosen to **strengthen** the requested product without narrowing its intended scope.

## Fixed interpretation of the prompt

### 1) Product shape
- HarmonyHub is a **single secure multi-tenant web application** serving both performing-arts directory workflows and concession meal fulfillment.
- It is delivered as a **Vue.js frontend + FastAPI backend + PostgreSQL** system.
- It is intended to run in **connected and intermittently connected on-prem environments**, including support for **self-signed HTTPS certificates**.

### 2) Tenant and domain hierarchy
- Primary tenant boundary is **Organization**.
- Within an organization, the main domain hierarchy is:
  - **Organization**
  - **Project / Program**
  - **Event**
  - **Store / Kitchen context** for concession operations
- Tenant isolation is enforced at the **organization** level first, with additional scoping across **project/program**, **event**, and **store** contexts.
- Safe default: users are typically scoped to a single organization tenant and may have access to one or more projects, events, and store contexts within that tenant unless a broader cross-tenant model is intentionally designed.

### 3) Roles and baseline permissions
- **Student**: browse permitted directory/repertoire content, maintain profile details relevant to participation, place/manage own orders, maintain own address book, view own pickup/delivery status.
- **Referee**: limited roster visibility and limited meal ordering; can view only event data explicitly granted to support staff.
- **Staff**: operate programs and kitchen workflows, manage featured entries, allowlists/blocklists, slot capacity, delivery zones, imports, duplicate resolution, fulfillment, and operational views.
- **Administrator**: tenant owner with full tenant-scoped administration, RBAC management, scoped ABAC policy management, exports, audit access, and account control.
- Permission evaluation is **default deny**.
- When ABAC is enabled for a tenant or specific surface, it acts as an additional constraint on RBAC-granted access.

### 4) Authentication and account security
- Authentication uses **local username/password**.
- Passwords are stored using a strong salted password hashing scheme; safe default is **Argon2id**.
- Optional offline MFA is implemented using **TOTP**, configurable per tenant or per user policy.
- Brute-force protection locks an account for **15 minutes after 5 failed attempts**.
- Session handling uses secure cookies/session tokens with CSRF protection for browser-authenticated flows.
- Users land on the **event dashboard** after successful sign-in, selecting or resuming their most relevant permitted event context.

### 5) Offline-ready interpretation
- Clarified requirement from user input: the first version must support **full offline queueing**.
- The implementation should achieve this through an offline-capable web architecture; a PWA/service-worker approach is the strongest default, but the requirement is the behavior rather than the label.
- The app caches core assets and recently accessed data required for primary workflows.
- **Reads remain available offline** when previously synchronized.
- **Writes are queued locally** when safe to defer, then synchronized when connectivity returns.
- Offline queueing applies to at least:
  - profile-safe edits,
  - address-book changes,
  - draft order actions,
  - selected staff operational actions that do not require immediate cross-user conflict resolution.
- Server-validated actions that cannot be safely finalized offline are held as **pending sync** and shown clearly in the UI.
- Conflict policy is conservative: **server truth wins for contested capacity/inventory/security decisions**, while preserving client intent for manual resolution where needed.

### 6) Directory and repertoire behavior
- Users can search and filter by **actor, repertoire item, tags, region, and availability windows**.
- Availability windows are interpreted as **time-ranged performer availability entries** and can be filtered by overlap with a requested time window.
- Result cards always respect permission masking.
- Contact details remain **masked by default** and are revealed only when the user has explicit permission to view sensitive contact data.
- Repertoire items may include **song metadata where applicable**, consistent with the prompt.

### 7) Recommendations behavior
- Recommendations are configurable and derived from:
  - **popularity over the last 30 days**,
  - **recent activity in the last 72 hours**,
  - **tag matching**.
- Staff can pin featured entries that appear ahead of algorithmic recommendations where configured.
- Allowlists/blocklists are enforced before recommendation display for restricted pairings.
- Safe precedence rule:
  - **blocklist overrides allowlist**,
  - pinned items must still satisfy permission and restriction rules,
  - recommendations never reveal masked data to unauthorized users.

### 8) Meal ordering and fulfillment model
- Orders support **pickup or delivery**.
- Users maintain an address book using **US-style addresses**.
- Checkout requires a valid fulfillment mode, selected slot, and any required address/delivery-zone match.
- Scheduling uses **15-minute slots**.
- Staff configure slot capacity as a maximum meal count per slot.
- If capacity is exceeded during checkout or sync reconciliation, the UI blocks confirmation and suggests the **next available slot**.
- Meal-ready estimates are recalculated from current kitchen workload and shown as dynamic ETAs.
- Pickup handoff uses a **rotating 6-digit pickup code** shown on the order screen and verified by staff at handoff.
- Safe default for rotation: keep the rotating code verifiable during normal handoff without creating operator friction.
- The order domain should use a clear state model that covers checkout through fulfillment and cancellation.

### 9) Delivery zones and fees
- Clarified implementation choice from user input: first-version delivery-zone assignment is **ZIP-code based**.
- Staff manage ZIP-to-zone mappings and flat fees.
- Pickup is modeled as a zero-fee fulfillment mode, not a delivery zone requirement.
- If no ZIP match exists for delivery, checkout blocks delivery and offers pickup or address correction.

### 10) Imports, deduplication, and account control
- Staff can bulk import members and rosters from CSV.
- Ingestion is layered exactly as prompted:
  - raw import preserved unchanged,
  - normalization/parsing layer,
  - processed/searchable tables.
- Duplicate handling supports operator-reviewed merges with audit history.
- Undo is available where safe and permitted, especially for merge and account-status actions when downstream integrity is not compromised.
- Freezing an account prevents sign-in and privileged actions immediately while retaining auditability and historical records.
- In-app status feedback must clearly show import progress, import errors, merge outcomes, freeze state, and undo availability.

### 11) Data model and storage defaults
- PostgreSQL is the local system of record.
- Core transactional entities use normalized relational tables.
- Flexible profile attributes, tags, and recommendation signals use **JSONB** where appropriate.
- Search-responsiveness under bulk load is supported through targeted indexes and partitioning across **repertoire item, time, and user** dimensions, aligned to the prompt.
- Audit and ingestion data remain queryable without weakening tenant isolation.

### 12) API and transport security
- Backend exposes **REST-style FastAPI endpoints** over site-wide HTTPS.
- Self-signed certificate support is treated as a supported deployment mode, not a test-only exception.
- Strict input validation is enforced server-side.
- Anti-replay protection uses **nonces plus a 5-minute timestamp window** on protected operations.
- API rate limits default to:
  - **60 requests/minute per user**
  - **300 requests/minute per device IP**
- Export actions require explicit permission and are always audited.

### 13) Row/column security interpretation
- Tenant isolation applies to organization/project/store contexts.
- Optional ABAC rules control menu visibility, API access, and row-/column-level scope tied to **department, grade, and class** dimensions.
- Safe default implementation target:
  - enforce data scopes at service/query level,
  - hide unauthorized fields before serialization,
  - reflect effective scope in the UI so masking and partial visibility are intentional and explainable.

### 14) Sensitive data handling
- Sensitive fields are encrypted at rest.
- Sensitive values are masked in logs and UI unless explicit permission allows display.
- Logs must avoid plaintext secrets, full passwords, MFA secrets, full sensitive contact data, and unnecessary personal address detail.
- SHA-256 fingerprints are stored for uploaded files to support tamper detection.

### 15) File upload interpretation
- Approved file types are **CSV, PDF, JPG, PNG** only.
- Maximum upload size is **25 MB**.
- Validation includes:
  - MIME/type allowlist,
  - file extension checks,
  - magic-byte validation,
  - SHA-256 fingerprinting.
- No external scanning service is assumed or required.
- Upload failures must return clear, safe user feedback.

### 16) Auditing, retention, backup, and recovery
- Auditing covers logins, permission changes, imports/exports, fulfillment steps, and admin actions.
- Audit retention target is **12 months**.
- Clarified implementation choice from user input: nightly local backups are supported through built-in product-managed jobs.
- Clarified implementation choice from user input: recovery drills are recorded in-product and expected on a **quarterly** basis.
- Backup and recovery records are tenant-aware where applicable and operator-visible to authorized admins/staff.

### 17) Logging and observability
- Both backend and frontend should emit operationally useful logs/events for authentication, sync, import, ordering, fulfillment, and authorization failures.
- Observability must be privacy-conscious and consistent with masking rules.
- Background jobs (backup, sync processing, imports) should expose status visible to authorized operators.

### 18) UX defaults that strengthen the prompt
- Event dashboard is the primary landing surface after sign-in.
- UI should make role scope obvious, especially where data is masked or partially visible.
- Offline state, queued actions, sync progress, and sync conflicts must be visible and understandable.
- Capacity failures and next-slot suggestions should occur inline during ordering, not only after submit.
- Import/merge/freeze actions should provide explicit success/failure status and audit traceability.

### 19) Safe engineering assumptions for delivery
- Use a modern Vue stack appropriate for robust offline-capable behavior.
- Prefer a clear component system and strong form validation.

## Remaining intentional non-expansions
These are not treated as blockers because the prompt does not require finer product-policy choices upfront:
- exact visual branding/theme direction,
- exact ETA formula internals as long as workload-based dynamic updates are real,
- exact duplicate-merge heuristics as long as operator-reviewed merge flows are implemented,
- exact backup media handling UX beyond recording designated offline-medium drill evidence.

## Clarification approval checkpoint
If approved, development should proceed using all defaults above as the binding interpretation of the prompt.
