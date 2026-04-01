import { expect, test } from '@playwright/test'

import { checkpointScreenshot } from './support/artifacts'
import { loginAs } from './support/auth'

test('administrator integrated flow: policy management UI plus operations accountability controls', async ({ page }) => {
  const uniqueId = Date.now()
  const e2eSurface = `e2e-surface-${uniqueId}`

  await loginAs(page, 'admin', 'admin123!')
  await checkpointScreenshot(page, 'admin', 'dashboard')

  await expect(page.getByRole('link', { name: 'Recommendations' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Fulfillment' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Imports & Accounts' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Operations' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Policy Management' })).toBeVisible()

  await page.getByRole('link', { name: 'Policy Management' }).click()
  await expect(page.getByRole('heading', { name: 'Manage scoped ABAC policy surfaces and rules.' })).toBeVisible()

  const surfacesSection = page.locator('.panel-section').filter({ hasText: 'Surface enable/disable' })
  await surfacesSection.getByLabel('Surface key').fill(e2eSurface)
  await surfacesSection.getByRole('button', { name: 'Upsert surface' }).click()

  const surfaceRow = surfacesSection.locator('.row-list li').filter({ hasText: e2eSurface }).first()
  await expect(surfaceRow).toContainText('enabled')

  await surfaceRow.getByRole('button', { name: 'Disable surface' }).click()
  await expect(surfaceRow).toContainText('disabled')

  await surfaceRow.getByRole('button', { name: 'Enable surface' }).click()
  await expect(surfaceRow).toContainText('enabled')

  const rulesSection = page.locator('.panel-section').filter({ hasText: 'Rule list' })
  await rulesSection.getByLabel('Rule surface').selectOption(e2eSurface)
  await rulesSection.getByLabel('Rule action').fill('view')
  await rulesSection.getByRole('button', { name: 'Load rules' }).click()

  const createRuleSection = page.locator('.panel-section').filter({ hasText: 'Create rule' })
  await createRuleSection.getByLabel('Create surface').fill(e2eSurface)
  await createRuleSection.getByLabel('Create action').fill('view')
  await createRuleSection.getByLabel('Effect').selectOption('deny')
  await createRuleSection.getByLabel('Priority').fill('11')
  await createRuleSection.getByLabel('Role (optional)').fill('student')
  await createRuleSection.getByRole('button', { name: 'Create rule' }).click()

  const createdRuleRow = rulesSection.locator('.row-list li').filter({ hasText: `${e2eSurface} · view` }).first()
  await expect(createdRuleRow).toContainText('DENY')

  const simulationSection = page.locator('.panel-section').filter({ hasText: 'Simulation' })
  await simulationSection.getByLabel('Sim surface').fill(e2eSurface)
  await simulationSection.getByLabel('Sim action').fill('view')
  await simulationSection.getByLabel('Sim role').fill('student')
  await simulationSection.getByRole('button', { name: 'Run simulation' }).click()
  await expect(simulationSection.locator('[aria-label="Simulation result"]')).toContainText(/Allowed:\s*no/i)

  await createdRuleRow.getByRole('button', { name: 'Delete rule' }).click()
  await expect(rulesSection.locator('.row-list li').filter({ hasText: `${e2eSurface} · view` })).toHaveCount(0)
  await checkpointScreenshot(page, 'admin', 'policy-management')

  await page.getByRole('link', { name: 'Operations' }).click()
  await expect(page.getByRole('heading', { name: 'Audit trails, exports, backups, and recovery drills' })).toBeVisible()

  const exportSection = page.locator('.panel-section').filter({ hasText: 'Directory exports' })
  await exportSection.getByRole('button', { name: 'Generate directory CSV' }).click()
  await expect(exportSection.locator('ul.run-list li').first()).toBeVisible({ timeout: 20_000 })

  const backupSection = page.locator('.panel-section').filter({ hasText: 'Backups' })
  await backupSection.getByRole('button', { name: 'Run backup now' }).click()
  await expect(backupSection.locator('ul.run-list li').first()).toBeVisible({ timeout: 30_000 })

  const drillSection = page.locator('.panel-section').filter({ hasText: 'Recovery drills' })
  await drillSection.getByLabel('Scenario').fill(`E2E recovery drill ${uniqueId}`)
  await drillSection.getByLabel('Status').selectOption('passed')
  await drillSection.getByLabel('Notes').fill('Integrated verification drill recorded by Playwright')
  await drillSection.getByRole('button', { name: 'Record drill' }).click()
  await expect(drillSection.locator('ul.run-list')).toContainText(`E2E recovery drill ${uniqueId}`)

  const auditSection = page.locator('.panel-section').filter({ hasText: 'Audit events' })
  await auditSection.getByLabel('Action prefix').fill('policy.abac.')
  await auditSection.getByRole('button', { name: 'Apply filters' }).click()
  await expect(auditSection.locator('ul.run-list')).toContainText('policy.abac.', { timeout: 20_000 })

  await checkpointScreenshot(page, 'admin', 'operations-controls')
})
