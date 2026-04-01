import type {
  AddressBookEntry,
  AddressBookEntryInput,
  ActiveContext,
  ContextChoice,
  DashboardResponse,
  DeliveryZone,
  DeliveryZoneInput,
  DuplicateStatus,
  DirectoryRecommendationsResponse,
  DirectoryContactRevealResponse,
  DirectoryEntryDetail,
  DirectorySearchFilters,
  DirectorySearchResponse,
  FeaturedPin,
  FulfillmentQueueOrder,
  FulfillmentTransitionStatus,
  ImportBatch,
  ImportBatchDetail,
  ImportBatchUpload,
  ImportDuplicateCandidate,
  ImportKind,
  MergeDuplicateResponse,
  MePayload,
  PairingRule,
  AccountStatus,
  AuditEvent,
  BackupRun,
  AbacRule,
  AbacRuleCreateInput,
  AbacSimulationRequestInput,
  AbacSimulationResponse,
  AbacSurfaceSetting,
  AbacSurfaceUpsertInput,
  MenuItem,
  DirectoryExportResponse,
  Order,
  OrderLineInput,
  OrderQuote,
  OrderType,
  PickupCodeIssueResponse,
  RecommendationConfig,
  RecommendationConfigUpdate,
  RecommendationScopeType,
  RepertoireRecommendationsResponse,
  RecoveryDrillCreateInput,
  RecoveryDrillRun,
  RepertoireItemDetail,
  RepertoireSearchFilters,
  RepertoireSearchResponse,
  SlotCapacity,
  SlotCapacityInput,
  ExportRun,
  OperationsStatus,
} from '@/types'

const API_BASE = '/api/v1'

export class ApiError extends Error {
  code: string
  status: number
  details: Record<string, unknown>

  constructor(message: string, code: string, status: number, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

function getCookie(name: string): string | null {
  const found = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))

  return found ? decodeURIComponent(found.split('=').slice(1).join('=')) : null
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function request<T>(
  path: string,
  method: HttpMethod = 'GET',
  body?: unknown,
  includeReplayHeaders = false,
): Promise<T> {
  const csrf = getCookie('hh_csrf')
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }

  if (csrf && method !== 'GET') {
    headers['X-CSRF-Token'] = csrf
  }

  if (includeReplayHeaders) {
    headers['X-Request-Nonce'] = crypto.randomUUID()
    headers['X-Request-Timestamp'] = new Date().toISOString()
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = payload?.error ?? {}
    throw new ApiError(
      error.message ?? `Request failed (${response.status})`,
      error.code ?? 'UNKNOWN_ERROR',
      response.status,
      error.details ?? {},
    )
  }

  return response.json() as Promise<T>
}

async function requestForm<T>(path: string, formData: FormData, includeReplayHeaders = false): Promise<T> {
  const csrf = getCookie('hh_csrf')
  const headers: HeadersInit = {}

  if (csrf) {
    headers['X-CSRF-Token'] = csrf
  }
  if (includeReplayHeaders) {
    headers['X-Request-Nonce'] = crypto.randomUUID()
    headers['X-Request-Timestamp'] = new Date().toISOString()
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const error = payload?.error ?? {}
    throw new ApiError(
      error.message ?? `Request failed (${response.status})`,
      error.code ?? 'UNKNOWN_ERROR',
      response.status,
      error.details ?? {},
    )
  }

  return response.json() as Promise<T>
}

function buildQuery(filters: Record<string, string | string[] | number | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '') {
      continue
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item.trim().length > 0) {
          params.append(key, item.trim())
        }
      }
      continue
    }
    params.append(key, String(value))
  }

  const query = params.toString()
  return query.length > 0 ? `?${query}` : ''
}

export async function login(username: string, password: string, totpCode?: string): Promise<MePayload> {
  const payload: Record<string, string> = { username, password }
  if (totpCode) {
    payload.totp_code = totpCode
  }
  await request('/auth/login', 'POST', payload)
  return me()
}

export async function logout(): Promise<void> {
  await request('/auth/logout', 'POST', undefined, true)
}

export async function me(): Promise<MePayload> {
  return request('/auth/me')
}

export async function fetchAvailableContexts(): Promise<ContextChoice[]> {
  return request('/contexts/available')
}

export async function setActiveContext(context: ActiveContext): Promise<ActiveContext> {
  const response = await request<{ status: string; active_context: ActiveContext }>(
    '/contexts/active',
    'POST',
    {
      organization_id: context.organization_id,
      program_id: context.program_id,
      event_id: context.event_id,
      store_id: context.store_id,
    },
    true,
  )
  return response.active_context
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  return request('/dashboard/event')
}

export async function fetchDirectory(filters: DirectorySearchFilters): Promise<DirectorySearchResponse> {
  return request(`/directory/search${buildQuery(filters)}`)
}

export async function fetchDirectoryEntry(entryId: string): Promise<DirectoryEntryDetail> {
  return request(`/directory/${entryId}`)
}

export async function revealDirectoryContact(entryId: string): Promise<DirectoryContactRevealResponse> {
  return request(`/directory/${entryId}/reveal-contact`, 'POST', {}, true)
}

export async function fetchRepertoire(filters: RepertoireSearchFilters): Promise<RepertoireSearchResponse> {
  return request(`/repertoire/search${buildQuery(filters)}`)
}

export async function fetchRepertoireItem(itemId: string): Promise<RepertoireItemDetail> {
  return request(`/repertoire/${itemId}`)
}

export async function fetchDirectoryRecommendations(filters: {
  tags?: string[]
  repertoire_item_id?: string
  limit?: number
}): Promise<DirectoryRecommendationsResponse> {
  return request(`/recommendations/directory${buildQuery(filters)}`)
}

export async function fetchRepertoireRecommendations(filters: {
  tags?: string[]
  directory_entry_id?: string
  limit?: number
}): Promise<RepertoireRecommendationsResponse> {
  return request(`/recommendations/repertoire${buildQuery(filters)}`)
}

export async function fetchRecommendationConfig(scope: RecommendationScopeType): Promise<RecommendationConfig> {
  return request(`/recommendations/config${buildQuery({ scope })}`)
}

export async function fetchEffectiveRecommendationConfig(): Promise<RecommendationConfig> {
  return request('/recommendations/config/effective')
}

export async function updateRecommendationConfig(payload: RecommendationConfigUpdate): Promise<RecommendationConfig> {
  return request('/recommendations/config', 'PUT', payload, true)
}

export async function pinFeaturedTarget(
  targetId: string,
  payload: { surface: 'directory' | 'repertoire'; expires_at?: string },
): Promise<FeaturedPin> {
  return request(`/recommendations/featured/${targetId}`, 'POST', payload, true)
}

export async function unpinFeaturedTarget(targetId: string, surface: 'directory' | 'repertoire'): Promise<void> {
  await request(`/recommendations/featured/${targetId}${buildQuery({ surface })}`, 'DELETE', undefined, true)
}

export async function listFeaturedPins(surface: 'directory' | 'repertoire'): Promise<FeaturedPin[]> {
  return request(`/recommendations/featured${buildQuery({ surface })}`)
}

export async function listPairingRules(effect?: 'allow' | 'block'): Promise<PairingRule[]> {
  return request(`/pairing-rules${buildQuery({ effect })}`)
}

export async function createAllowlistRule(payload: {
  directory_entry_id: string
  repertoire_item_id: string
  note?: string
}): Promise<PairingRule> {
  return request('/pairing-rules/allowlist', 'POST', payload, true)
}

export async function createBlocklistRule(payload: {
  directory_entry_id: string
  repertoire_item_id: string
  note?: string
}): Promise<PairingRule> {
  return request('/pairing-rules/blocklist', 'POST', payload, true)
}

export async function deletePairingRule(ruleId: string): Promise<void> {
  await request(`/pairing-rules/${ruleId}`, 'DELETE', undefined, true)
}

export async function fetchMenuItems(): Promise<MenuItem[]> {
  return request('/menu/items')
}

export async function listAddresses(): Promise<AddressBookEntry[]> {
  return request('/addresses')
}

export async function createAddress(payload: AddressBookEntryInput): Promise<AddressBookEntry> {
  return request('/addresses', 'POST', payload, true)
}

export async function updateAddress(addressId: string, payload: AddressBookEntryInput): Promise<AddressBookEntry> {
  return request(`/addresses/${addressId}`, 'PUT', payload, true)
}

export async function deleteAddress(addressId: string): Promise<void> {
  await request(`/addresses/${addressId}`, 'DELETE', undefined, true)
}

export async function listDeliveryZones(): Promise<DeliveryZone[]> {
  return request('/scheduling/delivery-zones')
}

export async function createDeliveryZone(payload: DeliveryZoneInput): Promise<DeliveryZone> {
  return request('/scheduling/delivery-zones', 'POST', payload, true)
}

export async function updateDeliveryZone(zoneId: string, payload: DeliveryZoneInput): Promise<DeliveryZone> {
  return request(`/scheduling/delivery-zones/${zoneId}`, 'PUT', payload, true)
}

export async function deleteDeliveryZone(zoneId: string): Promise<void> {
  await request(`/scheduling/delivery-zones/${zoneId}`, 'DELETE', undefined, true)
}

export async function listSlotCapacities(forDate?: string): Promise<SlotCapacity[]> {
  return request(`/scheduling/slot-capacities${buildQuery({ for_date: forDate })}`)
}

export async function upsertSlotCapacity(payload: SlotCapacityInput): Promise<SlotCapacity> {
  return request('/scheduling/slot-capacities', 'PUT', payload, true)
}

export async function deleteSlotCapacity(slotStart: string): Promise<void> {
  await request(`/scheduling/slot-capacities${buildQuery({ slot_start: slotStart })}`, 'DELETE', undefined, true)
}

export async function createOrderDraft(payload: {
  order_type: OrderType
  slot_start: string
  address_book_entry_id?: string
  lines: OrderLineInput[]
}): Promise<Order> {
  return request('/orders/drafts', 'POST', payload, true)
}

export async function updateOrderDraft(
  orderId: string,
  payload: {
    order_type: OrderType
    slot_start: string
    address_book_entry_id?: string
    lines: OrderLineInput[]
  },
): Promise<Order> {
  return request(`/orders/${orderId}/draft`, 'PUT', payload, true)
}

export async function listMyOrders(): Promise<Order[]> {
  return request('/orders/mine')
}

export async function getMyOrder(orderId: string): Promise<Order> {
  return request(`/orders/${orderId}`)
}

export async function quoteOrder(orderId: string): Promise<OrderQuote> {
  return request(`/orders/${orderId}/quote`, 'POST', undefined, true)
}

export async function confirmOrder(orderId: string): Promise<Order> {
  return request(`/orders/${orderId}/confirm`, 'POST', undefined, true)
}

export async function cancelOrder(orderId: string, reason?: string): Promise<Order> {
  return request(`/orders/${orderId}/cancel`, 'POST', { reason }, true)
}

export async function issuePickupCode(orderId: string): Promise<PickupCodeIssueResponse> {
  return request(`/orders/${orderId}/pickup-code`, 'POST', undefined, true)
}

export async function fetchPickupFulfillmentQueue(): Promise<FulfillmentQueueOrder[]> {
  return request('/fulfillment/queues/pickup')
}

export async function fetchDeliveryFulfillmentQueue(): Promise<FulfillmentQueueOrder[]> {
  return request('/fulfillment/queues/delivery')
}

export async function transitionFulfillmentOrder(
  orderId: string,
  payload: { target_status: FulfillmentTransitionStatus; cancel_reason?: string },
): Promise<Order> {
  return request(`/fulfillment/orders/${orderId}/transition`, 'POST', payload, true)
}

export async function verifyPickupCodeForHandoff(orderId: string, code: string): Promise<Order> {
  return request(`/fulfillment/orders/${orderId}/verify-pickup-code`, 'POST', { code }, true)
}

export async function uploadImportBatch(kind: ImportKind, file: File): Promise<ImportBatchUpload> {
  const formData = new FormData()
  formData.append('kind', kind)
  formData.append('file', file)
  return requestForm('/imports/batches/upload', formData, true)
}

export async function listImportBatches(): Promise<ImportBatch[]> {
  return request('/imports/batches')
}

export async function getImportBatchDetail(batchId: string): Promise<ImportBatchDetail> {
  return request(`/imports/batches/${batchId}`)
}

export async function normalizeImportBatch(batchId: string): Promise<ImportBatch> {
  return request(`/imports/batches/${batchId}/normalize`, 'POST', undefined, true)
}

export async function applyImportBatch(batchId: string): Promise<ImportBatch> {
  return request(`/imports/batches/${batchId}/apply`, 'POST', undefined, true)
}

export async function listImportDuplicates(status?: DuplicateStatus[]): Promise<ImportDuplicateCandidate[]> {
  return request(`/imports/duplicates${buildQuery({ status })}`)
}

export async function mergeImportDuplicate(duplicateId: string, note?: string): Promise<MergeDuplicateResponse> {
  return request(`/imports/duplicates/${duplicateId}/merge`, 'POST', { note }, true)
}

export async function ignoreImportDuplicate(duplicateId: string): Promise<ImportDuplicateCandidate> {
  return request(`/imports/duplicates/${duplicateId}/ignore`, 'POST', undefined, true)
}

export async function undoImportMerge(mergeActionId: string, reason?: string): Promise<MergeDuplicateResponse> {
  return request(`/imports/merges/${mergeActionId}/undo`, 'POST', { reason }, true)
}

export async function listAccounts(): Promise<AccountStatus[]> {
  return request('/accounts/users')
}

export async function freezeAccount(userId: string, reason: string): Promise<AccountStatus> {
  return request(`/accounts/users/${userId}/freeze`, 'POST', { reason }, true)
}

export async function unfreezeAccount(userId: string, reason?: string): Promise<AccountStatus> {
  return request(`/accounts/users/${userId}/unfreeze`, 'POST', { reason }, true)
}

export async function fetchOperationsStatus(): Promise<OperationsStatus> {
  return request('/operations/status')
}

export async function listAuditEvents(filters: {
  action_prefix?: string
  actor_user_id?: string
  target_type?: string
  target_id?: string
  start_at?: string
  end_at?: string
  limit?: number
}): Promise<AuditEvent[]> {
  return request(`/operations/audit-events${buildQuery(filters)}`)
}

export async function createDirectoryExport(includeSensitive: boolean): Promise<DirectoryExportResponse> {
  return request('/operations/exports/directory-csv', 'POST', { include_sensitive: includeSensitive }, true)
}

export async function listExportRuns(): Promise<ExportRun[]> {
  return request('/operations/exports/runs')
}

export async function triggerBackupRun(copyToOfflineMedium = true): Promise<BackupRun> {
  return request('/operations/backups/run', 'POST', { copy_to_offline_medium: copyToOfflineMedium }, true)
}

export async function listBackupRuns(): Promise<BackupRun[]> {
  return request('/operations/backups/runs')
}

export async function createRecoveryDrill(payload: RecoveryDrillCreateInput): Promise<RecoveryDrillRun> {
  return request('/operations/recovery-drills', 'POST', payload, true)
}

export async function listRecoveryDrills(): Promise<RecoveryDrillRun[]> {
  return request('/operations/recovery-drills')
}

export async function listAbacSurfaces(): Promise<AbacSurfaceSetting[]> {
  return request('/admin/policies/abac/surfaces')
}

export async function upsertAbacSurface(surface: string, payload: AbacSurfaceUpsertInput): Promise<AbacSurfaceSetting> {
  return request(`/admin/policies/abac/surfaces/${surface}`, 'PUT', payload, true)
}

export async function listAbacRules(surface: string, action: string): Promise<AbacRule[]> {
  return request(`/admin/policies/abac/rules${buildQuery({ surface, action })}`)
}

export async function createAbacRule(payload: AbacRuleCreateInput): Promise<AbacRule> {
  return request('/admin/policies/abac/rules', 'POST', payload, true)
}

export async function deleteAbacRule(ruleId: string): Promise<void> {
  await request(`/admin/policies/abac/rules/${ruleId}`, 'DELETE', undefined, true)
}

export async function simulateAbac(payload: AbacSimulationRequestInput): Promise<AbacSimulationResponse> {
  return request('/admin/policies/simulate', 'POST', payload)
}
