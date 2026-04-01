import type {
  AddressBookEntryInput,
  QueueConflict,
  QueueEntityType,
  QueuedMutation,
  QueueActionType,
  OrderLineInput,
  OrderType,
} from '@/types'

import { getBrowserStorage, readJson, type StorageLike, writeJson } from '@/offline/storage'

const WRITE_QUEUE_KEY = 'hh_write_queue_v1'

type ApiLikeError = {
  code?: string
  status?: number
  message?: string
  details?: Record<string, unknown>
}

type QueueResultCommitted = {
  outcome: 'committed'
}

type QueueResultConflict = {
  outcome: 'conflict'
  conflict: QueueConflict
}

type QueueResultRetry = {
  outcome: 'retry'
  message: string
}

export type QueueProcessResult = QueueResultCommitted | QueueResultConflict | QueueResultRetry

export type QueueProcessor = (item: QueuedMutation) => Promise<QueueProcessResult>

export type QueueEnqueuePayload = {
  action: QueueActionType
  entity_type: QueueEntityType
  entity_id: string
  context_key: string
  user_id: string
  payload: QueuedMutation['payload']
}

function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `queue-${Math.random().toString(36).slice(2, 12)}`
}

function nowIso(): string {
  return new Date().toISOString()
}

function normalizeQueue(queue: QueuedMutation[] | null): QueuedMutation[] {
  if (!Array.isArray(queue)) {
    return []
  }
  return queue
    .filter((item) => item && typeof item.id === 'string')
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
}

function parseConflict(error: ApiLikeError): QueueConflict {
  return {
    code: error.code ?? 'SYNC_CONFLICT',
    message: error.message ?? 'Server rejected queued mutation',
    details: error.details ?? {},
  }
}

function isRetryableError(error: ApiLikeError): boolean {
  if (typeof error.status !== 'number') {
    return true
  }
  if (error.status >= 500 || error.status === 429) {
    return true
  }
  return false
}

export class WriteQueue {
  constructor(
    private readonly storage: StorageLike = getBrowserStorage(),
    private readonly key: string = WRITE_QUEUE_KEY,
  ) {}

  listAll(): QueuedMutation[] {
    return normalizeQueue(readJson<QueuedMutation[]>(this.storage, this.key))
  }

  listForScope(scopeKey: string, userId: string): QueuedMutation[] {
    return this.listAll().filter((item) => item.context_key === scopeKey && item.user_id === userId)
  }

  enqueue(input: QueueEnqueuePayload): QueuedMutation {
    const item: QueuedMutation = {
      id: newId(),
      action: input.action,
      entity_type: input.entity_type,
      entity_id: input.entity_id,
      context_key: input.context_key,
      user_id: input.user_id,
      status: 'local_queued',
      attempts: 0,
      conflict: null,
      last_error: null,
      created_at: nowIso(),
      updated_at: nowIso(),
      payload: input.payload,
    }
    const queue = this.listAll()
    queue.push(item)
    this.persist(queue)
    return item
  }

  removeById(id: string): void {
    const queue = this.listAll().filter((item) => item.id !== id)
    this.persist(queue)
  }

  removeWhere(predicate: (item: QueuedMutation) => boolean): void {
    const queue = this.listAll().filter((item) => !predicate(item))
    this.persist(queue)
  }

  removeForUser(userId: string): void {
    this.removeWhere((item) => item.user_id === userId)
  }

  removeForScope(scopeKey: string, userId: string): void {
    this.removeWhere((item) => item.context_key === scopeKey && item.user_id === userId)
  }

  update(id: string, updater: (item: QueuedMutation) => QueuedMutation): QueuedMutation | null {
    const queue = this.listAll()
    const index = queue.findIndex((item) => item.id === id)
    if (index < 0) {
      return null
    }
    const updated = updater(queue[index])
    queue[index] = {
      ...updated,
      updated_at: nowIso(),
    }
    this.persist(queue)
    return queue[index]
  }

  markLocalQueued(id: string): void {
    this.update(id, (item) => ({
      ...item,
      status: 'local_queued',
      conflict: null,
      last_error: null,
    }))
  }

  async processScope(scopeKey: string, userId: string, processor: QueueProcessor): Promise<void> {
    const candidates = this.listForScope(scopeKey, userId).filter((item) =>
      ['local_queued', 'failed_retrying', 'syncing'].includes(item.status),
    )

    for (const item of candidates) {
      this.update(item.id, (prev) => ({ ...prev, status: 'syncing', last_error: null }))
      try {
        const result = await processor(item)
        if (result.outcome === 'committed') {
          this.removeById(item.id)
          continue
        }
        if (result.outcome === 'conflict') {
          this.update(item.id, (prev) => ({
            ...prev,
            status: 'conflict',
            conflict: result.conflict,
            last_error: result.conflict.message,
            attempts: prev.attempts + 1,
          }))
          continue
        }

        this.update(item.id, (prev) => ({
          ...prev,
          status: 'failed_retrying',
          last_error: result.message,
          attempts: prev.attempts + 1,
        }))
      } catch (error) {
        const apiError = error as ApiLikeError
        if (isRetryableError(apiError)) {
          this.update(item.id, (prev) => ({
            ...prev,
            status: 'failed_retrying',
            last_error: apiError.message ?? 'Sync retry scheduled',
            attempts: prev.attempts + 1,
          }))
          continue
        }

        this.update(item.id, (prev) => ({
          ...prev,
          status: 'conflict',
          conflict: parseConflict(apiError),
          last_error: apiError.message ?? 'Server rejected queued mutation',
          attempts: prev.attempts + 1,
        }))
      }
    }
  }

  private persist(queue: QueuedMutation[]): void {
    writeJson(this.storage, this.key, normalizeQueue(queue))
  }
}

export const writeQueueSingleton = new WriteQueue()

export function isRetryableQueueError(error: unknown): boolean {
  const apiError = error as ApiLikeError
  return isRetryableError(apiError)
}

export function toQueueConflict(error: unknown): QueueConflict {
  return parseConflict(error as ApiLikeError)
}

export function draftPayload(
  orderId: string,
  input: { order_type: OrderType; slot_start: string; address_book_entry_id?: string; lines: OrderLineInput[] },
): QueuedMutation['payload'] {
  return {
    order_id: orderId,
    input,
  }
}

export function addressCreatePayload(localAddressId: string, input: AddressBookEntryInput): QueuedMutation['payload'] {
  return {
    local_address_id: localAddressId,
    input,
  }
}
