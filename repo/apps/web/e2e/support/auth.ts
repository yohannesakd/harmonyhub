import { expect, type Page } from '@playwright/test'

export async function loginAs(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Event operations dashboard' })).toBeVisible()
}

export async function logout(page: Page): Promise<void> {
  const signOut = page.getByRole('button', { name: 'Sign out' })
  if (await signOut.isVisible()) {
    await signOut.click()
    await expect(page).toHaveURL(/\/login$/)
  }
}

export function alignedLocalSlot(minutesFromNow = 30): string {
  const now = new Date()
  const roundedMinutes = Math.floor(now.getMinutes() / 15) * 15
  now.setMinutes(roundedMinutes, 0, 0)
  now.setMinutes(now.getMinutes() + minutesFromNow)

  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
}

export function alignedIsoSlot(minutesFromNow = 30): string {
  const local = alignedLocalSlot(minutesFromNow)
  return new Date(local).toISOString()
}
