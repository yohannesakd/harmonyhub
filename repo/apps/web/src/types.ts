export type Role = 'student' | 'referee' | 'staff' | 'administrator'

export type UserSummary = {
  id: string
  username: string
  is_active: boolean
  mfa_totp_enabled: boolean
}

export type ContextChoice = {
  organization_id: string
  organization_name: string
  program_id: string
  program_name: string
  event_id: string
  event_name: string
  store_id: string
  store_name: string
  role: Role
}

export type ActiveContext = {
  organization_id: string
  program_id: string
  event_id: string
  store_id: string
  role: Role
}

export type AuthPayload = {
  user: UserSummary
  active_context: ActiveContext | null
  permissions: string[]
}

export type MePayload = AuthPayload & {
  available_contexts: ContextChoice[]
}

export type DashboardResponse = {
  event_name: string
  store_name: string
  organization_name: string
  user_role: Role
  permissions: string[]
  abac_enforced: boolean
  notes: string[]
}

export type DirectoryContact = {
  email: string | null
  phone: string | null
  address_line1: string | null
  masked: boolean
}

export type AvailabilityWindow = {
  starts_at: string
  ends_at: string
}

export type DirectoryEntryCard = {
  id: string
  display_name: string
  stage_name: string | null
  region: string
  tags: string[]
  repertoire: string[]
  availability_windows: AvailabilityWindow[]
  contact: DirectoryContact
  can_reveal_contact: boolean
}

export type DirectoryEntryDetail = DirectoryEntryCard & {
  biography: string | null
}

export type DirectorySearchResponse = {
  results: DirectoryEntryCard[]
  total: number
}

export type DirectoryContactRevealResponse = {
  entry_id: string
  contact: DirectoryContact
}

export type DirectorySearchFilters = {
  q?: string
  actor?: string
  repertoire?: string
  tags?: string[]
  region?: string
  availability_start?: string
  availability_end?: string
}

export type RepertoireItemCard = {
  id: string
  title: string
  composer: string | null
  tags: string[]
  performer_names: string[]
  regions: string[]
}

export type RepertoireItemDetail = RepertoireItemCard & {
  performer_count: number
}

export type RepertoireSearchResponse = {
  results: RepertoireItemCard[]
  total: number
}

export type RepertoireSearchFilters = {
  q?: string
  actor?: string
  repertoire?: string
  tags?: string[]
  region?: string
  availability_start?: string
  availability_end?: string
}

export type RecommendationScopeType = 'organization' | 'program' | 'event_store'

export type RecommendationEnabledModes = {
  popularity_30d: boolean
  recent_activity_72h: boolean
  tag_match: boolean
}

export type RecommendationWeights = {
  popularity_30d: number
  recent_activity_72h: number
  tag_match: number
}

export type RecommendationScope = {
  scope: RecommendationScopeType
  organization_id: string
  program_id?: string | null
  event_id?: string | null
  store_id?: string | null
}

export type RecommendationConfig = {
  id: string | null
  scope: RecommendationScope
  inherited_from_scope: RecommendationScopeType | null
  enabled_modes: RecommendationEnabledModes
  weights: RecommendationWeights
  pins_enabled: boolean
  max_pins: number
  pin_ttl_hours: number | null
  enforce_pairing_rules: boolean
  allow_staff_event_store_manage: boolean
  updated_at: string
}

export type RecommendationConfigUpdate = {
  scope: RecommendationScopeType
  enabled_modes: RecommendationEnabledModes
  weights: RecommendationWeights
  pins_enabled: boolean
  max_pins: number
  pin_ttl_hours: number | null
  enforce_pairing_rules: boolean
  allow_staff_event_store_manage: boolean
}

export type RecommendationScoreBreakdown = {
  popularity_30d: number
  recent_activity_72h: number
  tag_match: number
  total: number
}

export type DirectoryRecommendationItem = {
  entry_id: string
  display_name: string
  region: string
  tags: string[]
  repertoire: string[]
  contact: DirectoryContact
  pinned: boolean
  score: RecommendationScoreBreakdown
}

export type RepertoireRecommendationItem = {
  repertoire_item_id: string
  title: string
  composer: string | null
  tags: string[]
  performers: string[]
  pinned: boolean
  score: RecommendationScoreBreakdown
}

export type DirectoryRecommendationsResponse = {
  config_scope: RecommendationScopeType
  results: DirectoryRecommendationItem[]
}

export type RepertoireRecommendationsResponse = {
  config_scope: RecommendationScopeType
  results: RepertoireRecommendationItem[]
}

export type FeaturedPin = {
  id: string
  surface: 'directory' | 'repertoire'
  directory_entry_id: string | null
  repertoire_item_id: string | null
  expires_at: string | null
  created_at: string
}

export type PairingRule = {
  id: string
  effect: 'allow' | 'block'
  directory_entry_id: string
  repertoire_item_id: string
  note: string | null
  created_at: string
}

export type MenuItem = {
  id: string
  name: string
  description: string | null
  price_cents: number
  is_active: boolean
}

export type AddressBookEntry = {
  id: string
  label: string
  recipient_name: string
  line1: string
  line2: string | null
  city: string
  state: string
  postal_code: string
  phone: string | null
  is_default: boolean
  sync_state?: SyncStatus
  sync_error?: string | null
  local_only?: boolean
}

export type AddressBookEntryInput = {
  label: string
  recipient_name: string
  line1: string
  line2?: string | null
  city: string
  state: string
  postal_code: string
  phone?: string | null
  is_default: boolean
}

export type DeliveryZone = {
  id: string
  zip_code: string
  flat_fee_cents: number
  is_active: boolean
}

export type DeliveryZoneInput = {
  zip_code: string
  flat_fee_cents: number
  is_active: boolean
}

export type SlotCapacity = {
  id: string
  slot_start: string
  capacity: number
}

export type SlotCapacityInput = {
  slot_start: string
  capacity: number
}

export type OrderLineInput = {
  menu_item_id: string
  quantity: number
}

export type OrderLine = {
  id: string
  menu_item_id: string
  item_name: string
  quantity: number
  unit_price_cents: number
  line_total_cents: number
}

export type OrderState =
  | 'draft'
  | 'quoted'
  | 'confirmed'
  | 'preparing'
  | 'ready_for_pickup'
  | 'handed_off'
  | 'ready_for_dispatch'
  | 'out_for_delivery'
  | 'delivered'
  | 'conflict'
  | 'cancelled'
export type OrderType = 'pickup' | 'delivery'

export type Order = {
  id: string
  status: OrderState
  order_type: OrderType
  slot_start: string
  subtotal_cents: number
  delivery_fee_cents: number
  total_cents: number
  eta_minutes: number | null
  address_book_entry_id: string | null
  delivery_zone_id: string | null
  conflict_reason: string | null
  cancel_reason: string | null
  quote_expires_at: string | null
  confirmed_at: string | null
  preparing_at: string | null
  ready_at: string | null
  dispatched_at: string | null
  handed_off_at: string | null
  delivered_at: string | null
  pickup_code_expires_at: string | null
  pickup_code_rotated_at: string | null
  created_at: string
  updated_at: string
  lines: OrderLine[]
  sync_state?: SyncStatus
  sync_error?: string | null
  local_only?: boolean
}

export type OrderQuote = {
  order_id: string
  status: OrderState
  order_type: OrderType
  slot_start: string
  subtotal_cents: number
  delivery_fee_cents: number
  total_cents: number
  eta_minutes: number | null
  quote_expires_at: string | null
  lines: OrderLine[]
  next_available_slots: string[]
  conflict_reason: string | null
}

export type PickupCodeIssueResponse = {
  order_id: string
  code: string
  expires_at: string
  ttl_seconds: number
}

export type FulfillmentTransitionStatus =
  | 'preparing'
  | 'ready_for_pickup'
  | 'ready_for_dispatch'
  | 'out_for_delivery'
  | 'delivered'
  | 'cancelled'

export type FulfillmentAddressSummary = {
  recipient_name: string
  line1: string
  line2: string | null
  city: string
  state: string
  postal_code: string
  phone: string | null
}

export type FulfillmentQueueOrder = {
  id: string
  user_id: string
  username: string
  status: OrderState
  order_type: OrderType
  slot_start: string
  subtotal_cents: number
  delivery_fee_cents: number
  total_cents: number
  eta_minutes: number | null
  confirmed_at: string | null
  preparing_at: string | null
  ready_at: string | null
  dispatched_at: string | null
  handed_off_at: string | null
  delivered_at: string | null
  updated_at: string
  lines: OrderLine[]
  address: FulfillmentAddressSummary | null
}

export type ImportKind = 'member' | 'roster'
export type ImportBatchStatus = 'uploaded' | 'normalized' | 'needs_review' | 'processed' | 'failed'
export type DuplicateStatus = 'open' | 'merged' | 'ignored' | 'undo_applied'

export type UploadedAsset = {
  id: string
  filename: string
  extension: string
  content_type: string
  detected_type: string
  size_bytes: number
  sha256: string
  import_kind: ImportKind | null
  created_at: string
}

export type ImportBatch = {
  id: string
  uploaded_asset_id: string
  kind: ImportKind
  status: ImportBatchStatus
  total_rows: number
  valid_rows: number
  issue_count: number
  duplicate_count: number
  processed_count: number
  validation_issues_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
  processed_at: string | null
}

export type ImportNormalizedRow = {
  id: string
  row_number: number
  raw_row_json: Record<string, string>
  normalized_json: Record<string, string> | null
  issues_json: Record<string, unknown> | null
  is_valid: boolean
  processing_status: string
  effect_target_type: string | null
  effect_target_id: string | null
}

export type ImportBatchDetail = {
  batch: ImportBatch
  rows: ImportNormalizedRow[]
}

export type ImportBatchUpload = {
  upload: UploadedAsset
  batch: ImportBatch
}

export type ImportDuplicateCandidate = {
  id: string
  batch_id: string
  normalized_row_id: string
  target_directory_entry_id: string
  target_display_name: string
  reason: string
  status: DuplicateStatus
  merge_action_id: string | null
  normalized_json: Record<string, string> | null
  created_at: string
  updated_at: string
}

export type MergeDuplicateResponse = {
  merge_action_id: string
  duplicate_id: string
  applied_changes: Record<string, unknown>
  merged_at: string
}

export type AccountStatus = {
  id: string
  username: string
  is_active: boolean
  is_frozen: boolean
  frozen_at: string | null
  freeze_reason: string | null
  frozen_by_user_id: string | null
  unfrozen_at: string | null
  unfrozen_by_user_id: string | null
}

export type AuditEvent = {
  id: string
  actor_user_id: string | null
  actor_role: string | null
  action: string
  target_type: string | null
  target_id: string | null
  details_json: Record<string, unknown> | null
  created_at: string
}

export type ExportRun = {
  id: string
  export_type: string
  status: string
  include_sensitive: boolean
  row_count: number
  file_size_bytes: number
  sha256: string
  created_at: string
  completed_at: string
}

export type DirectoryExportResponse = {
  export_run: ExportRun
  filename: string
  download_path: string
}

export type BackupRun = {
  id: string
  trigger_type: string
  status: string
  file_path: string
  file_size_bytes: number
  sha256: string
  offline_copy_path: string | null
  offline_copy_verified: boolean
  verification_json: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export type RecoveryDrillStatus = 'passed' | 'failed' | 'inconclusive'

export type RecoveryDrillRun = {
  id: string
  backup_run_id: string | null
  performed_by_user_id: string
  scenario: string
  status: RecoveryDrillStatus
  evidence_json: Record<string, unknown> | null
  notes: string | null
  performed_at: string
}

export type RecoveryDrillCreateInput = {
  backup_run_id?: string | null
  scenario: string
  status: RecoveryDrillStatus
  evidence_json?: Record<string, unknown> | null
  notes?: string | null
}

export type AuditRetentionStatus = {
  retention_days: number
  cutoff_at: string
  events_older_than_retention: number
}

export type RecoveryDrillCompliance = {
  interval_days: number
  status: 'current' | 'overdue'
  latest_performed_at: string | null
  due_at: string | null
  days_until_due: number | null
  days_overdue: number
}

export type OperationsStatus = {
  pending_import_batches: number
  open_import_duplicates: number
  pickup_queue_count: number
  delivery_queue_count: number
  order_conflict_count: number
  latest_backup: BackupRun | null
  latest_recovery_drill: RecoveryDrillRun | null
  audit_retention: AuditRetentionStatus
  recovery_drill_compliance: RecoveryDrillCompliance
}

export type AbacSurfaceSetting = {
  id: string
  organization_id: string
  surface: string
  enabled: boolean
}

export type AbacSurfaceUpsertInput = {
  enabled: boolean
}

export type AbacRuleEffect = 'allow' | 'deny'

export type AbacRule = {
  id: string
  organization_id: string
  surface: string
  action: string
  effect: AbacRuleEffect
  priority: number
  role: string | null
  subject_department: string | null
  subject_grade: string | null
  subject_class: string | null
  program_id: string | null
  event_id: string | null
  store_id: string | null
  resource_department: string | null
  resource_grade: string | null
  resource_class: string | null
  resource_field: string | null
}

export type AbacRuleCreateInput = {
  surface: string
  action: string
  effect: AbacRuleEffect
  priority: number
  role?: string
  subject_department?: string
  subject_grade?: string
  subject_class?: string
  program_id?: string
  event_id?: string
  store_id?: string
  resource_department?: string
  resource_grade?: string
  resource_class?: string
  resource_field?: string
}

export type AbacSimulationRequestInput = {
  surface: string
  action: string
  role: string
  context: {
    program_id?: string
    event_id?: string
    store_id?: string
  }
  subject?: {
    department?: string
    grade?: string
    class_code?: string
  }
  resource?: {
    department?: string
    grade?: string
    class_code?: string
    field?: string
  }
}

export type AbacSimulationResponse = {
  allowed: boolean
  enforced: boolean
  reason: string
  matched_rule_id: string | null
}

export type SyncStatus = 'local_queued' | 'syncing' | 'server_committed' | 'conflict' | 'failed_retrying'

export type QueueActionType =
  | 'address.create'
  | 'address.update'
  | 'address.delete'
  | 'order.draft.save'
  | 'order.confirm'

export type QueueEntityType = 'address' | 'order'

export type QueueConflict = {
  code: string
  message: string
  details: Record<string, unknown>
}

export type AddressCreateQueuePayload = {
  local_address_id: string
  input: AddressBookEntryInput
}

export type AddressUpdateQueuePayload = {
  address_id: string
  input: AddressBookEntryInput
}

export type AddressDeleteQueuePayload = {
  address_id: string
}

export type OrderDraftSaveQueuePayload = {
  order_id: string
  input: {
    order_type: OrderType
    slot_start: string
    address_book_entry_id?: string
    lines: OrderLineInput[]
  }
}

export type OrderConfirmQueuePayload = {
  order_id: string
}

export type EncryptedQueuePayload = {
  encrypted: true
  version: 1
  algorithm: 'AES-GCM'
  iv_b64: string
  ciphertext_b64: string
}

export type QueuedMutation = {
  id: string
  action: QueueActionType
  entity_type: QueueEntityType
  entity_id: string
  context_key: string
  user_id: string
  status: SyncStatus
  attempts: number
  conflict: QueueConflict | null
  last_error: string | null
  created_at: string
  updated_at: string
  payload:
    | AddressCreateQueuePayload
    | AddressUpdateQueuePayload
    | AddressDeleteQueuePayload
    | OrderDraftSaveQueuePayload
    | OrderConfirmQueuePayload
    | EncryptedQueuePayload
}
