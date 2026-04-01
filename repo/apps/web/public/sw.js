const SHELL_CACHE = 'hh-shell-v2'

const SHELL_ASSETS = ['/', '/index.html']

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE)
      await cache.addAll(SHELL_ASSETS)
      await self.skipWaiting()
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
        const names = await caches.keys()
        await Promise.all(names.filter((name) => ![SHELL_CACHE].includes(name)).map((name) => caches.delete(name)))
        await self.clients.claim()
      })(),
  )
})

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request)
    if (response && response.ok) {
      const cache = await caches.open(cacheName)
      await cache.put(request, response.clone())
    }
    return response
  } catch {
    const cached = await caches.match(request)
    if (cached) {
      return cached
    }
    throw new Error('network-failed')
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)

  if (request.method !== 'GET') {
    return
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request)
          const cache = await caches.open(SHELL_CACHE)
          await cache.put('/index.html', response.clone())
          return response
        } catch {
          const cached = await caches.match('/index.html')
          if (cached) {
            return cached
          }
          return Response.error()
        }
      })(),
    )
    return
  }

  if (url.origin === self.location.origin && ['script', 'style', 'font', 'image'].includes(request.destination)) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request)
        if (cached) {
          return cached
        }
        try {
          const response = await fetch(request)
          if (response && response.ok) {
            const cache = await caches.open(SHELL_CACHE)
            await cache.put(request, response.clone())
          }
          return response
        } catch {
          return Response.error()
        }
      })(),
    )
  }
})

self.addEventListener('message', (event) => {
  const messageType = event?.data?.type
  if (messageType !== 'hh:auth-boundary') {
    return
  }

  event.waitUntil(
    (async () => {
      const names = await caches.keys()
      await Promise.all(names.filter((name) => name !== SHELL_CACHE).map((name) => caches.delete(name)))
    })(),
  )
})
