const US_STATE_CODES = new Set([
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
  'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
  'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
  'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
  'DC',
])

export function normalizeUsState(value: string): string {
  return value.trim().toUpperCase()
}

export function isValidUsState(value: string): boolean {
  return US_STATE_CODES.has(normalizeUsState(value))
}

export function normalizeUsPostalCode(value: string): string {
  const trimmed = value.trim()
  if (/^\d{9}$/.test(trimmed)) {
    return `${trimmed.slice(0, 5)}-${trimmed.slice(5)}`
  }
  return trimmed
}

export function isValidUsPostalCode(value: string): boolean {
  const normalized = normalizeUsPostalCode(value)
  return /^\d{5}(-\d{4})?$/.test(normalized)
}

export function normalizeUsPhone(value: string): string | null {
  const digits = value.replace(/\D/g, '')
  if (digits.length === 0) {
    return null
  }

  const tenDigits = digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits
  if (tenDigits.length !== 10) {
    return null
  }

  return `${tenDigits.slice(0, 3)}-${tenDigits.slice(3, 6)}-${tenDigits.slice(6)}`
}
