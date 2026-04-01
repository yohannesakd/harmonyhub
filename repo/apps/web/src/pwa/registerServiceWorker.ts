export async function registerServiceWorker(): Promise<void> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return
  }

  if (import.meta.env.DEV) {
    return
  }

  const baseUrl = import.meta.env.BASE_URL || '/'
  const scriptUrl = `${baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl}/sw.js`

  try {
    await navigator.serviceWorker.register(scriptUrl)
  } catch {
    // Registration failures should not block app usage.
  }
}

export async function notifyAuthBoundaryChange(): Promise<void> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return
  }

  const registration = await navigator.serviceWorker.getRegistration().catch(() => null)
  const target = registration?.active ?? navigator.serviceWorker.controller
  if (!target) {
    return
  }

  target.postMessage({ type: 'hh:auth-boundary' })
}
