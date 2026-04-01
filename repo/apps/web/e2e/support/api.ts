import { expect, request } from '@playwright/test'

import { alignedIsoSlot } from './auth'

type ApiSession = {
  api: Awaited<ReturnType<typeof request.newContext>>
  csrf: string
}

const DEFAULT_API_BASE_URL = process.env.E2E_API_BASE_URL || 'https://localhost:9443'

function securityHeaders(csrf: string): Record<string, string> {
  return {
    'X-CSRF-Token': csrf,
    'X-Request-Nonce': crypto.randomUUID(),
    'X-Request-Timestamp': new Date().toISOString(),
  }
}

export async function createApiSession(
  username: string,
  password: string,
  baseURL = DEFAULT_API_BASE_URL,
): Promise<ApiSession> {
  const api = await request.newContext({ baseURL, ignoreHTTPSErrors: true })
  const login = await api.post('/api/v1/auth/login', { data: { username, password } })
  expect(login.ok()).toBeTruthy()
  const payload = (await login.json()) as { csrf_token: string }
  return { api, csrf: payload.csrf_token }
}

export async function createConfirmedPickupOrderWithCode(
  baseURL = DEFAULT_API_BASE_URL,
): Promise<{ orderId: string; code: string }> {
  const { api, csrf } = await createApiSession('student', 'stud123!', baseURL)

  const menu = await api.get('/api/v1/menu/items')
  expect(menu.ok()).toBeTruthy()
  const menuItems = (await menu.json()) as Array<{ id: string }>
  expect(menuItems.length).toBeGreaterThan(0)

  const draft = await api.post('/api/v1/orders/drafts', {
    headers: securityHeaders(csrf),
    data: {
      order_type: 'pickup',
      slot_start: alignedIsoSlot(360),
      lines: [{ menu_item_id: menuItems[0].id, quantity: 1 }],
    },
  })
  expect(draft.ok()).toBeTruthy()
  const draftPayload = (await draft.json()) as { id: string }
  const orderId = draftPayload.id

  const quote = await api.post(`/api/v1/orders/${orderId}/quote`, {
    headers: securityHeaders(csrf),
  })
  expect(quote.ok()).toBeTruthy()

  const confirm = await api.post(`/api/v1/orders/${orderId}/confirm`, {
    headers: securityHeaders(csrf),
  })
  expect(confirm.ok()).toBeTruthy()

  const pickupCode = await api.post(`/api/v1/orders/${orderId}/pickup-code`, {
    headers: securityHeaders(csrf),
  })
  expect(pickupCode.ok()).toBeTruthy()
  const pickupCodePayload = (await pickupCode.json()) as { code: string }

  await api.dispose()
  return { orderId, code: pickupCodePayload.code }
}

export async function createQuotedPickupOrder(baseURL = DEFAULT_API_BASE_URL): Promise<{ orderId: string }> {
  const { api, csrf } = await createApiSession('student', 'stud123!', baseURL)

  const menu = await api.get('/api/v1/menu/items')
  expect(menu.ok()).toBeTruthy()
  const menuItems = (await menu.json()) as Array<{ id: string }>
  expect(menuItems.length).toBeGreaterThan(0)

  const draft = await api.post('/api/v1/orders/drafts', {
    headers: securityHeaders(csrf),
    data: {
      order_type: 'pickup',
      slot_start: alignedIsoSlot(360),
      lines: [{ menu_item_id: menuItems[0].id, quantity: 1 }],
    },
  })
  expect(draft.ok()).toBeTruthy()
  const draftPayload = (await draft.json()) as { id: string }
  const orderId = draftPayload.id

  const quote = await api.post(`/api/v1/orders/${orderId}/quote`, {
    headers: securityHeaders(csrf),
  })
  expect(quote.ok()).toBeTruthy()

  await api.dispose()
  return { orderId }
}

export async function issuePickupCodeForOrder(
  orderId: string,
  baseURL = DEFAULT_API_BASE_URL,
): Promise<{ code: string }> {
  const { api, csrf } = await createApiSession('student', 'stud123!', baseURL)
  const pickupCode = await api.post(`/api/v1/orders/${orderId}/pickup-code`, {
    headers: securityHeaders(csrf),
  })
  expect(pickupCode.ok()).toBeTruthy()
  const payload = (await pickupCode.json()) as { code: string }
  await api.dispose()
  return payload
}

export async function getStudentOrderStatus(
  orderId: string,
  baseURL = DEFAULT_API_BASE_URL,
): Promise<string> {
  const { api } = await createApiSession('student', 'stud123!', baseURL)
  const response = await api.get(`/api/v1/orders/${orderId}`)
  expect(response.ok()).toBeTruthy()
  const payload = (await response.json()) as { status: string }
  await api.dispose()
  return payload.status
}
