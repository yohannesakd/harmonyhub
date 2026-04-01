import { ApiError } from '@/services/api'

export function toDisplayErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message || fallback
  }

  if (error instanceof Error) {
    const normalized = error.message.toLowerCase()
    if (normalized.includes('failed to fetch') || normalized.includes('network')) {
      return 'Network connection unavailable. Retry when you are back online.'
    }
    return error.message || fallback
  }

  return fallback
}
