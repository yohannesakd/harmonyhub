import { mkdir } from 'node:fs/promises'
import path from 'node:path'

import type { Page } from '@playwright/test'

const SCREENSHOT_ROOT = path.resolve(process.cwd(), 'e2e-artifacts', 'screenshots')

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

export async function checkpointScreenshot(page: Page, flow: string, checkpoint: string): Promise<string> {
  const dir = path.join(SCREENSHOT_ROOT, slug(flow))
  await mkdir(dir, { recursive: true })
  const filePath = path.join(dir, `${Date.now()}-${slug(checkpoint)}.png`)
  await page.screenshot({ path: filePath, fullPage: true })
  return filePath
}
