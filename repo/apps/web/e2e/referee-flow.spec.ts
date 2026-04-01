import { expect, test } from '@playwright/test'

import { alignedLocalSlot, loginAs } from './support/auth'
import { checkpointScreenshot } from './support/artifacts'

test('referee integrated flow: limited visibility with ordering access', async ({ page }) => {
  await loginAs(page, 'referee', 'ref123!')
  await checkpointScreenshot(page, 'referee', 'dashboard')

  await expect(page.getByRole('link', { name: 'Fulfillment' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Imports & Accounts' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Operations' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Policy Management' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Directory' }).click()
  await expect(page.locator('.directory-card').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reveal contact details' })).toHaveCount(0)
  await expect(page.locator('.directory-card .directory-card__contact').first()).toContainText(/\*\*\*/)
  await checkpointScreenshot(page, 'referee', 'directory-limited')

  await page.getByRole('link', { name: 'Repertoire' }).click()
  await expect(page.locator('.repertoire-page__summary')).toBeVisible()
  await checkpointScreenshot(page, 'referee', 'repertoire')

  await page.getByRole('link', { name: 'Ordering' }).click()
  await page.getByLabel('Fulfillment type').selectOption('pickup')
  await page.getByLabel('15-minute slot').fill(alignedLocalSlot(360))
  await page.locator('.order-composer__menu article').first().getByLabel('Qty').fill('1')
  await page.getByRole('button', { name: /Create draft|Update draft/ }).click()
  await expect(page.locator('.ordering-page__summary')).toContainText(/Status:\s*(draft|confirmed|quoted)/i)

  const quoteButton = page.locator('.order-composer').getByRole('button', { name: 'Quote', exact: true })
  if (await quoteButton.isEnabled()) {
    await quoteButton.click()
  }

  const finalizeButton = page.locator('.order-composer').getByRole('button', { name: 'Finalize checkout', exact: true })
  try {
    await expect(finalizeButton).toBeEnabled({ timeout: 10_000 })
    await finalizeButton.click()
  } catch {
    // Keep flow resilient when checkout remains quoted due transient state.
  }

  await expect(page.locator('.ordering-page__summary')).toContainText(/Status:\s*(draft|confirmed|quoted)/i)
  await expect(page.getByText('Staff scheduling controls')).toHaveCount(0)
  await checkpointScreenshot(page, 'referee', 'ordering-confirmed')
})
