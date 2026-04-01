import { expect, test } from '@playwright/test'

import { loginAs } from './support/auth'
import { createQuotedPickupOrder } from './support/api'
import { checkpointScreenshot } from './support/artifacts'

test('student integrated flow: browse, checkout, and offline queue', async ({ page, context, baseURL }) => {
  const { orderId } = await createQuotedPickupOrder()
  const uniqueId = Date.now()

  await loginAs(page, 'student', 'stud123!')
  await checkpointScreenshot(page, 'student', 'dashboard')

  await page.getByRole('link', { name: 'Directory' }).click()
  await expect(page.getByRole('heading', { name: 'Find performers by repertoire, region, tags, and availability windows.' })).toBeVisible()
  await expect(page.locator('.directory-card').first()).toBeVisible()
  await expect(page.locator('.directory-card .directory-card__contact').first()).toContainText(/\*\*\*/)
  await checkpointScreenshot(page, 'student', 'directory-masked')

  await page.getByRole('link', { name: 'Repertoire' }).click()
  await expect(page.getByRole('heading', { name: 'Search repertoire by title, performer linkage, tags, region, and availability overlap.' })).toBeVisible()
  await expect(page.locator('.repertoire-page__summary')).toBeVisible()
  await checkpointScreenshot(page, 'student', 'repertoire')

  await context.setOffline(true)

  await page.getByRole('link', { name: 'Directory' }).click()
  await expect(page.getByText('Data source: cached offline snapshot')).toBeVisible()
  await expect(page.getByText('Offline: showing cached directory results for this context and filter set.')).toBeVisible()
  await expect(page.locator('.directory-card').first()).toBeVisible()
  await checkpointScreenshot(page, 'student', 'directory-offline-cached')

  await page.getByRole('link', { name: 'Repertoire' }).click()
  await expect(page.getByText('Data source: cached offline snapshot')).toBeVisible()
  await expect(page.getByText('Offline: showing cached repertoire results for this context and filter set.')).toBeVisible()
  await expect(page.locator('.repertoire-card').first()).toBeVisible()
  await checkpointScreenshot(page, 'student', 'repertoire-offline-cached')

  await context.setOffline(false)

  await page.getByRole('link', { name: 'Ordering' }).click()
  await expect(page.getByRole('heading', { name: 'Place pickup or delivery concession orders with real slot capacity checks.' })).toBeVisible()

  const addressLabel = `Student Home ${uniqueId}`
  await page.getByLabel('Label').fill(addressLabel)
  await page.getByLabel('Recipient').fill('Student Patron')
  await page.getByLabel('Line 1').fill('100 Main St')
  await page.getByLabel('City').fill('New York')
  await page.getByLabel('State').fill('NY')
  await page.getByLabel('ZIP').fill('10001')
  await page.getByLabel('Phone').fill('555-111-0000')
  await page.getByRole('button', { name: 'Add address' }).click()
  await expect(page.locator('.address-book__list')).toContainText(addressLabel)

  await page.getByRole('button', { name: new RegExp(orderId.slice(0, 8), 'i') }).click()
  await expect(page.locator('.ordering-page__summary')).toContainText(/Status:\s*quoted/i)

  await context.setOffline(true)

  const queuedAddressLabel = `Queued Offline ${uniqueId}`
  await page.getByLabel('Label').fill(queuedAddressLabel)
  await page.getByLabel('Recipient').fill('Offline Patron')
  await page.getByLabel('Line 1').fill('77 Offline Lane')
  await page.getByLabel('City').fill('New York')
  await page.getByLabel('State').fill('NY')
  await page.getByLabel('ZIP').fill('10001')
  await page.getByLabel('Phone').fill('555-111-9999')
  await page.getByRole('button', { name: 'Add address' }).click()
  await expect(page.getByText('Address change queued for sync.')).toBeVisible()

  await page.locator('.order-composer__menu article').first().getByLabel('Qty').fill('2')
  await page.getByRole('button', { name: 'Update draft', exact: true }).click()
  await expect(page.getByText('Draft write queued for sync.')).toBeVisible()

  const finalizeButton = page.locator('.order-composer').getByRole('button', { name: 'Queue finalize (offline)', exact: true })
  await expect(finalizeButton).toBeEnabled()
  await finalizeButton.click()

  await expect(page.getByText('Finalize action queued. Server will confirm or reject when reconnected.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Offline sync queue' })).toBeVisible()
  await expect(page.locator('.ordering-page__sync')).toContainText('address.create')
  await expect(page.locator('.ordering-page__sync')).toContainText('order.draft.save')
  await expect(page.locator('.ordering-page__sync')).toContainText('order.confirm')
  await expect(page.locator('.ordering-page__sync')).toContainText('local_queued')
  await checkpointScreenshot(page, 'student', 'offline-queue')

  await context.setOffline(false)
  await page.goto(`${baseURL}/dashboard`)
})
