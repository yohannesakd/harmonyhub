import { ApiError } from '@/services/api'
import { toDisplayErrorMessage } from '@/utils/displayErrors'

describe('toDisplayErrorMessage', () => {
  it('normalizes raw network fetch errors', () => {
    const message = toDisplayErrorMessage(new Error('Failed to fetch'), 'fallback')
    expect(message).toBe('Network connection unavailable. Retry when you are back online.')
  })

  it('preserves API error messages', () => {
    const message = toDisplayErrorMessage(new ApiError('Forbidden', 'FORBIDDEN', 403), 'fallback')
    expect(message).toBe('Forbidden')
  })
})
