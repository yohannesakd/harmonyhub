import { expect, test } from '@playwright/test'

import { alignedLocalSlot, loginAs } from './support/auth'
import { checkpointScreenshot } from './support/artifacts'
import { createConfirmedPickupOrderWithCode, getStudentOrderStatus, issuePickupCodeForOrder } from './support/api'

test('staff integrated flow: recommendations, scheduling, and account controls', async ({ page }) => {
  const uniqueId = Date.now()

  await loginAs(page, 'staff', 'staff123!')
  await expect(page.getByRole('link', { name: 'Policy Management' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Directory' }).click()
  const recommendationAction = page.locator('.recommendation-rail button').first()
  await expect(recommendationAction).toBeVisible()
  await recommendationAction.click()
  await expect(recommendationAction).toBeEnabled()
  await checkpointScreenshot(page, 'staff', 'directory-pinning')

  await page.getByRole('link', { name: 'Recommendations' }).click()
  await expect(
    page.getByRole('heading', {
      name: 'Recommendation management for delegated scoring, featured pins, and pairing rules.',
    }),
  ).toBeVisible()

  const ruleDeleteButtons = page.locator('.pairing-manager__rules li').getByRole('button', { name: 'Delete' })
  if ((await ruleDeleteButtons.count()) > 0) {
    const firstRule = page.locator('.pairing-manager__rules li').first()
    const firstRuleText = (await firstRule.textContent())?.trim() || ''
    await firstRule.getByRole('button', { name: 'Delete' }).click()
    await expect(page.locator('.pairing-manager__rules')).not.toContainText(firstRuleText)
  } else {
    await page.locator('.pairing-manager').getByLabel('Directory entry').selectOption({ index: 1 })
    await page.locator('.pairing-manager').getByLabel('Repertoire item').selectOption({ index: 1 })
    await page.getByRole('button', { name: 'Add allowlist rule' }).click()
    await expect(ruleDeleteButtons.first()).toBeVisible()
  }
  await checkpointScreenshot(page, 'staff', 'pairing-rule-managed')

  await page.getByRole('link', { name: 'Ordering' }).click()
  await expect(page.getByText('Staff scheduling controls')).toBeVisible()

  const zipCode = String(11000 + (uniqueId % 800))
  await page.locator('.zone-manager').getByLabel('ZIP').fill(zipCode)
  await page.locator('.zone-manager').getByLabel('Flat fee (cents)').fill('650')
  await page.getByRole('button', { name: 'Create / upsert zone' }).click()
  await expect(page.locator('.zone-manager ul')).toContainText(zipCode)

  await page.locator('.slot-manager').getByLabel('Slot start').fill(alignedLocalSlot(120))
  await page.locator('.slot-manager').getByLabel('Capacity').fill('7')
  await page.getByRole('button', { name: 'Upsert slot capacity' }).click()
  await expect(page.locator('.slot-manager ul')).toContainText('cap 7')
  await checkpointScreenshot(page, 'staff', 'scheduling-controls')

  await page.getByRole('link', { name: 'Imports & Accounts' }).click()
  const refereeRow = page.locator('.account-panel__list li').filter({ hasText: 'referee' }).first()
  await expect(refereeRow).toBeVisible()

  await refereeRow.getByPlaceholder('Freeze reason (required)').fill('Integrated verification freeze check')
  await refereeRow.getByRole('button', { name: 'Freeze' }).click()
  await expect(refereeRow).toContainText('Frozen')

  await refereeRow.getByPlaceholder('Unfreeze note (optional)').fill('Restore referee account state')
  await refereeRow.getByRole('button', { name: 'Unfreeze' }).click()
  await expect(refereeRow).toContainText('Active')
  await checkpointScreenshot(page, 'staff', 'account-freeze-unfreeze')
})

test('staff integrated flow: fulfillment queue transitions and pickup verification', async ({ page }) => {
  const { orderId } = await createConfirmedPickupOrderWithCode()

  await loginAs(page, 'staff', 'staff123!')
  await page.getByRole('link', { name: 'Fulfillment' }).click()
  await expect(page.getByRole('heading', { name: 'Run pickup and delivery queues with strict, service-aware status transitions.' })).toBeVisible()

  const orderRef = orderId.slice(0, 8)
  const pickupCard = page.locator('.queue-card').filter({ hasText: orderRef }).first()
  await expect(pickupCard).toBeVisible()

  await pickupCard.getByRole('button', { name: 'Start preparing' }).click()
  await expect(pickupCard).toContainText('preparing')

  await pickupCard.getByRole('button', { name: 'Mark ready for pickup' }).click()
  await expect(pickupCard).toContainText('ready_for_pickup')

  const { code } = await issuePickupCodeForOrder(orderId)

  await pickupCard.getByPlaceholder('6-digit code').fill(code)
  await pickupCard.getByRole('button', { name: 'Verify + hand off' }).click()

  await expect.poll(async () => getStudentOrderStatus(orderId)).toBe('handed_off')
  await checkpointScreenshot(page, 'staff', 'fulfillment-verified-handoff')
})
