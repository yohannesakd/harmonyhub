export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> & {
  key?: (index: number) => string | null
  length?: number
}

function noopStorage(): StorageLike {
  const memory = new Map<string, string>()
  return {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memory.set(key, value)
    },
    removeItem: (key: string) => {
      memory.delete(key)
    },
    key: (index: number) => [...memory.keys()][index] ?? null,
    get length() {
      return memory.size
    },
  }
}

export function getBrowserStorage(): StorageLike {
  if (typeof window === 'undefined' || !window.localStorage) {
    return noopStorage()
  }
  return window.localStorage
}

export function readJson<T>(storage: StorageLike, key: string): T | null {
  const raw = storage.getItem(key)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function writeJson(storage: StorageLike, key: string, value: unknown): void {
  storage.setItem(key, JSON.stringify(value))
}

export function listStorageKeys(storage: StorageLike): string[] {
  if (typeof storage.length !== 'number' || typeof storage.key !== 'function') {
    return []
  }

  const keys: string[] = []
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index)
    if (key) {
      keys.push(key)
    }
  }
  return keys
}
