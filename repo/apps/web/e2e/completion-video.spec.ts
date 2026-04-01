import { expect, request, test } from '@playwright/test'

import { alignedLocalSlot, loginAs, logout } from './support/auth'
import {
  createQuotedPickupOrder,
} from './support/api'

type ApiSession = {
  api: Awaited<ReturnType<typeof request.newContext>>
  csrf: string
}

const DEFAULT_API_BASE_URL = process.env.E2E_API_BASE_URL || 'https://localhost:9443'

function apiHeaders(csrf: string) {
  return {
    'X-CSRF-Token': csrf,
    'X-Request-Nonce': crypto.randomUUID(),
    'X-Request-Timestamp': new Date().toISOString(),
  }
}

async function createApiSessionForContext(
  username: string,
  password: string,
  match: { program: string; event: string; store: string },
): Promise<ApiSession> {
  const api = await request.newContext({ baseURL: DEFAULT_API_BASE_URL, ignoreHTTPSErrors: true })
  const login = await api.post('/api/v1/auth/login', { data: { username, password } })
  expect(login.ok()).toBeTruthy()
  const payload = (await login.json()) as { csrf_token: string }
  const csrf = payload.csrf_token

  const contextsResponse = await api.get('/api/v1/contexts/available')
  expect(contextsResponse.ok()).toBeTruthy()
  const contexts = (await contextsResponse.json()) as Array<{
    organization_id: string
    program_id: string
    event_id: string
    store_id: string
    program_name: string
    event_name: string
    store_name: string
  }>

  const target = contexts.find(
    (context) =>
      context.program_name === match.program && context.event_name === match.event && context.store_name === match.store,
  )
  expect(target).toBeTruthy()

  const setContext = await api.post('/api/v1/contexts/active', {
    headers: apiHeaders(csrf),
    data: {
      organization_id: target!.organization_id,
      program_id: target!.program_id,
      event_id: target!.event_id,
      store_id: target!.store_id,
    },
  })
  expect(setContext.ok()).toBeTruthy()

  return { api, csrf }
}

async function listAvailableContexts(username: string, password: string) {
  const api = await request.newContext({ baseURL: DEFAULT_API_BASE_URL, ignoreHTTPSErrors: true })
  const login = await api.post('/api/v1/auth/login', { data: { username, password } })
  expect(login.ok()).toBeTruthy()
  const contextsResponse = await api.get('/api/v1/contexts/available')
  expect(contextsResponse.ok()).toBeTruthy()
  const contexts = (await contextsResponse.json()) as Array<{
    organization_id: string
    program_id: string
    event_id: string
    store_id: string
    program_name: string
    event_name: string
    store_name: string
  }>
  await api.dispose()
  return contexts
}

async function findSharedStudentStaffContext() {
  const [studentContexts, staffContexts] = await Promise.all([
    listAvailableContexts('student', 'stud123!'),
    listAvailableContexts('staff', 'staff123!'),
  ])

  const shared = studentContexts.find((studentContext) =>
    staffContexts.some(
      (staffContext) =>
        staffContext.program_name === studentContext.program_name &&
        staffContext.event_name === studentContext.event_name &&
        staffContext.store_name === studentContext.store_name,
    ),
  )
  expect(shared).toBeTruthy()
  return {
    program: shared!.program_name,
    event: shared!.event_name,
    store: shared!.store_name,
  }
}

async function createConfirmedPickupOrderInContext(match: { program: string; event: string; store: string }) {
  const { api, csrf } = await createApiSessionForContext('student', 'stud123!', match)
  const menu = await api.get('/api/v1/menu/items')
  expect(menu.ok()).toBeTruthy()
  const menuItems = (await menu.json()) as Array<{ id: string }>
  expect(menuItems.length).toBeGreaterThan(0)

  const draft = await api.post('/api/v1/orders/drafts', {
    headers: apiHeaders(csrf),
    data: {
      order_type: 'pickup',
      slot_start: new Date(alignedLocalSlot(360)).toISOString(),
      lines: [{ menu_item_id: menuItems[0].id, quantity: 1 }],
    },
  })
  expect(draft.ok()).toBeTruthy()
  const draftPayload = (await draft.json()) as { id: string }

  const quote = await api.post(`/api/v1/orders/${draftPayload.id}/quote`, { headers: apiHeaders(csrf) })
  expect(quote.ok()).toBeTruthy()
  const confirm = await api.post(`/api/v1/orders/${draftPayload.id}/confirm`, { headers: apiHeaders(csrf) })
  expect(confirm.ok()).toBeTruthy()

  await api.dispose()
  return { orderId: draftPayload.id }
}

async function listPickupQueueInContext(match: { program: string; event: string; store: string }) {
  const { api } = await createApiSessionForContext('staff', 'staff123!', match)
  const response = await api.get('/api/v1/fulfillment/queues/pickup')
  expect(response.ok()).toBeTruthy()
  const payload = (await response.json()) as Array<{ id: string }>
  await api.dispose()
  return payload
}

async function issuePickupCodeInContext(
  orderId: string,
  match: { program: string; event: string; store: string },
): Promise<string> {
  const { api, csrf } = await createApiSessionForContext('student', 'stud123!', match)
  const response = await api.post(`/api/v1/orders/${orderId}/pickup-code`, { headers: apiHeaders(csrf) })
  expect(response.ok()).toBeTruthy()
  const payload = (await response.json()) as { code: string }
  await api.dispose()
  return payload.code
}

async function getOrderStatusInContext(
  orderId: string,
  match: { program: string; event: string; store: string },
): Promise<string> {
  const { api } = await createApiSessionForContext('student', 'stud123!', match)
  const response = await api.get(`/api/v1/orders/${orderId}`)
  expect(response.ok()).toBeTruthy()
  const payload = (await response.json()) as { status: string }
  await api.dispose()
  return payload.status
}

test.use({
  viewport: { width: 1440, height: 960 },
  video: { mode: 'on', size: { width: 1440, height: 960 } },
  screenshot: 'off',
  trace: 'off',
})

const pace = {
  short: 350,
  medium: 700,
  long: 1200,
}

async function rest(page: import('@playwright/test').Page, ms = pace.medium) {
  await page.waitForTimeout(ms)
}

async function moveMouseTo(page: import('@playwright/test').Page, locator: import('@playwright/test').Locator) {
  const box = await locator.boundingBox()
  if (!box) return
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 28 })
  await rest(page, 180)
}

async function humanClick(page: import('@playwright/test').Page, locator: import('@playwright/test').Locator) {
  await locator.scrollIntoViewIfNeeded()
  await rest(page, 220)
  await moveMouseTo(page, locator)
  await locator.click({ delay: 90 })
  await rest(page, pace.medium)
}

async function humanFill(
  page: import('@playwright/test').Page,
  locator: import('@playwright/test').Locator,
  value: string,
) {
  await locator.scrollIntoViewIfNeeded()
  await moveMouseTo(page, locator)
  await locator.click({ delay: 70 })
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
  await page.keyboard.press('Backspace')
  await page.keyboard.type(value, { delay: 55 })
  await rest(page, 200)
}

async function humanScroll(page: import('@playwright/test').Page, distance: number) {
  const step = distance > 0 ? 120 : -120
  let remaining = Math.abs(distance)
  while (remaining > 0) {
    await page.mouse.wheel(0, step)
    remaining -= Math.abs(step)
    await rest(page, 120)
  }
  await rest(page, 300)
}

async function hoverRead(page: import('@playwright/test').Page, locator: import('@playwright/test').Locator, ms = 900) {
  await locator.scrollIntoViewIfNeeded()
  await moveMouseTo(page, locator)
  await rest(page, ms)
}

test('record smooth completion walkthrough', async ({ page, context, baseURL }) => {
  test.setTimeout(15 * 60 * 1000)

  const uniqueId = Date.now()
  const { orderId: quotedOrderId } = await createQuotedPickupOrder()
  const sharedContext = await findSharedStudentStaffContext()

  // Student flow
  await loginAs(page, 'student', 'stud123!')
  await rest(page, pace.long)
  await hoverRead(page, page.getByRole('heading', { name: 'Event operations dashboard' }), 1300)

  const directoryLink = page.getByRole('link', { name: 'Directory' })
  await humanClick(page, directoryLink)
  await expect(page.getByRole('heading', { name: 'Find performers by repertoire, region, tags, and availability windows.' })).toBeVisible()
  await hoverRead(page, page.locator('.directory-card').first(), 1400)
  await humanScroll(page, 460)
  await humanScroll(page, -460)

  const repertoireLink = page.getByRole('link', { name: 'Repertoire' })
  await humanClick(page, repertoireLink)
  await expect(page.getByRole('heading', { name: 'Search repertoire by title, performer linkage, tags, region, and availability overlap.' })).toBeVisible()
  await hoverRead(page, page.locator('.repertoire-card').first(), 1200)

  const orderingLink = page.getByRole('link', { name: 'Ordering' })
  await humanClick(page, orderingLink)
  await expect(page.getByRole('heading', { name: 'Place pickup or delivery concession orders with real slot capacity checks.' })).toBeVisible()

  const addressLabel = `Demo Home ${uniqueId}`
  await humanFill(page, page.getByLabel('Label'), addressLabel)
  await humanFill(page, page.getByLabel('Recipient'), 'Student Patron')
  await humanFill(page, page.getByLabel('Line 1'), '100 Main St')
  await humanFill(page, page.getByLabel('City'), 'New York')
  await humanFill(page, page.getByLabel('State'), 'NY')
  await humanFill(page, page.getByLabel('ZIP'), '10001')
  await humanFill(page, page.getByLabel('Phone'), '5551110000')
  await humanClick(page, page.getByRole('button', { name: 'Add address' }))
  await expect(page.locator('.address-book__list')).toContainText(addressLabel)
  await hoverRead(page, page.locator('.address-book__list').locator('li').last(), 1000)

  await humanClick(page, page.getByRole('button', { name: new RegExp(quotedOrderId.slice(0, 8), 'i') }))
  await expect(page.locator('.ordering-page__summary')).toContainText(/Status:\s*quoted/i)
  await hoverRead(page, page.locator('.ordering-page__summary'), 1500)

  await context.setOffline(true)
  await rest(page, 600)
  await humanFill(page, page.getByLabel('Label'), `Queued Offline ${uniqueId}`)
  await humanFill(page, page.getByLabel('Recipient'), 'Offline Patron')
  await humanFill(page, page.getByLabel('Line 1'), '77 Offline Lane')
  await humanFill(page, page.getByLabel('City'), 'New York')
  await humanFill(page, page.getByLabel('State'), 'NY')
  await humanFill(page, page.getByLabel('ZIP'), '10001')
  await humanFill(page, page.getByLabel('Phone'), '5551119999')
  await humanClick(page, page.getByRole('button', { name: 'Add address' }))
  await expect(page.getByText('Address change queued for sync.')).toBeVisible()

  const qtyInput = page.locator('.order-composer__menu article').first().getByLabel('Qty')
  await humanFill(page, qtyInput, '2')
  await humanClick(page, page.getByRole('button', { name: 'Update draft', exact: true }))
  await expect(page.getByText('Draft write queued for sync.')).toBeVisible()

  await humanClick(page, page.locator('.order-composer').getByRole('button', { name: 'Queue finalize (offline)', exact: true }))
  await expect(page.getByRole('heading', { name: 'Offline sync queue' })).toBeVisible()
  await hoverRead(page, page.locator('.ordering-page__sync'), 1800)
  await context.setOffline(false)
  await rest(page, 1000)

  // Staff flow
  await logout(page)
  await loginAs(page, 'staff', 'staff123!')
  await rest(page, pace.long)

  const staffContext = page.getByLabel('Active context')
  const options = await staffContext.locator('option').allTextContents()
  const matchingIndex = options.findIndex(
    (option) =>
      option.includes(sharedContext.program) && option.includes(sharedContext.event) && option.includes(sharedContext.store),
  )
  expect(matchingIndex).toBeGreaterThanOrEqual(0)
  await staffContext.selectOption({ index: matchingIndex })
  await rest(page, 1000)

  let pickupQueue = await listPickupQueueInContext(sharedContext)
  if (pickupQueue.length === 0) {
    await createConfirmedPickupOrderInContext(sharedContext)
    pickupQueue = await listPickupQueueInContext(sharedContext)
  }
  expect(pickupQueue.length).toBeGreaterThan(0)
  const pickupOrderId = pickupQueue[0].id
  await rest(page, 600)

  await humanClick(page, page.getByRole('link', { name: 'Recommendations' }))
  await expect(page.getByRole('heading', { name: 'Recommendation management for delegated scoring, featured pins, and pairing rules.' })).toBeVisible()
  await hoverRead(page, page.locator('.pairing-manager'), 1200)

  await humanClick(page, page.getByRole('link', { name: 'Ordering' }))
  await expect(page.getByText('Staff scheduling controls')).toBeVisible()
  const zipCode = String(12000 + (uniqueId % 700))
  await humanFill(page, page.locator('.zone-manager').getByLabel('ZIP'), zipCode)
  await humanFill(page, page.locator('.zone-manager').getByLabel('Flat fee (cents)'), '650')
  await humanClick(page, page.getByRole('button', { name: 'Create / upsert zone' }))
  await expect(page.locator('.zone-manager ul')).toContainText(zipCode)

  await humanFill(page, page.locator('.slot-manager').getByLabel('Slot start'), alignedLocalSlot(120))
  await humanFill(page, page.locator('.slot-manager').getByLabel('Capacity'), '7')
  await humanClick(page, page.getByRole('button', { name: 'Upsert slot capacity' }))
  await hoverRead(page, page.locator('.slot-manager'), 1200)

  await humanClick(page, page.getByRole('link', { name: 'Fulfillment' }))
  await expect(page.getByRole('heading', { name: 'Run pickup and delivery queues with strict, service-aware status transitions.' })).toBeVisible()
  const pickupCard = page.locator('li').filter({ hasText: `#${pickupOrderId.slice(0, 8)}` }).first()
  await expect(pickupCard).toBeVisible({ timeout: 20_000 })
  await hoverRead(page, pickupCard, 900)
  await humanClick(page, pickupCard.getByRole('button', { name: 'Start preparing' }))
  await humanClick(page, pickupCard.getByRole('button', { name: 'Mark ready for pickup' }))
  const code = await issuePickupCodeInContext(pickupOrderId, sharedContext)
  await humanFill(page, pickupCard.getByPlaceholder('6-digit code'), code)
  await humanClick(page, pickupCard.getByRole('button', { name: 'Verify + hand off' }))
  await expect.poll(async () => getOrderStatusInContext(pickupOrderId, sharedContext)).toBe('handed_off')
  await hoverRead(page, page.getByRole('heading', { name: 'Pickup queue' }), 1200)

  // Admin flow
  await logout(page)
  await loginAs(page, 'admin', 'admin123!')
  await rest(page, pace.long)

  await humanClick(page, page.getByRole('link', { name: 'Policy Management' }))
  await expect(page.getByRole('heading', { name: 'Manage scoped ABAC policy surfaces and rules.' })).toBeVisible()
  const policySurface = `walkthrough-${uniqueId}`
  const surfacesSection = page.locator('.panel-section').filter({ hasText: 'Surface enable/disable' })
  await humanFill(page, surfacesSection.getByLabel('Surface key'), policySurface)
  await humanClick(page, surfacesSection.getByRole('button', { name: 'Upsert surface' }))
  const surfaceRow = surfacesSection.locator('.row-list li').filter({ hasText: policySurface }).first()
  await hoverRead(page, surfaceRow, 900)
  await humanClick(page, surfaceRow.getByRole('button', { name: 'Disable surface' }))
  await humanClick(page, surfaceRow.getByRole('button', { name: 'Enable surface' }))

  const simulationSection = page.locator('.panel-section').filter({ hasText: 'Simulation' })
  await humanFill(page, simulationSection.getByLabel('Sim surface'), policySurface)
  await humanFill(page, simulationSection.getByLabel('Sim action'), 'view')
  await humanFill(page, simulationSection.getByLabel('Sim role'), 'student')
  await humanClick(page, simulationSection.getByRole('button', { name: 'Run simulation' }))
  await hoverRead(page, simulationSection.locator('[aria-label="Simulation result"]'), 1200)

  await humanClick(page, page.getByRole('link', { name: 'Operations' }))
  await expect(page.getByRole('heading', { name: 'Audit trails, exports, backups, and recovery drills' })).toBeVisible()
  const exportSection = page.locator('.panel-section').filter({ hasText: 'Directory exports' })
  await humanClick(page, exportSection.getByRole('button', { name: 'Generate directory CSV' }))
  await expect(exportSection.locator('ul.run-list li').first()).toBeVisible({ timeout: 20_000 })

  const backupSection = page.locator('.panel-section').filter({ hasText: 'Backups' })
  await humanClick(page, backupSection.getByRole('button', { name: 'Run backup now' }))
  await expect(backupSection.locator('ul.run-list li').first()).toBeVisible({ timeout: 30_000 })

  const drillSection = page.locator('.panel-section').filter({ hasText: 'Recovery drills' })
  await humanFill(page, drillSection.getByLabel('Scenario'), `Walkthrough drill ${uniqueId}`)
  await humanClick(page, drillSection.getByLabel('Status'))
  await drillSection.getByLabel('Status').selectOption('passed')
  await rest(page, 200)
  await humanFill(page, drillSection.getByLabel('Notes'), 'Completion video walkthrough recorded with Playwright')
  await humanClick(page, drillSection.getByRole('button', { name: 'Record drill' }))
  await expect(drillSection.locator('ul.run-list')).toContainText(`Walkthrough drill ${uniqueId}`)
  await hoverRead(page, page.locator('.operations-page'), 1600)

  await rest(page, 1500)
  await page.goto(`${baseURL}/dashboard`)
  await rest(page, 1800)
})
