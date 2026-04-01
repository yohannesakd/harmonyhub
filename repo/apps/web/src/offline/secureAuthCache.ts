import type { MePayload } from '@/types'

const AUTH_BOOTSTRAP_CACHE_VERSION = 1 as const
const PBKDF2_ITERATIONS = 120_000
const PBKDF2_SALT_PREFIX = 'hh_auth_bootstrap_cache_v1'

export type EncryptedAuthBootstrapPayload = {
  encrypted: true
  version: 1
  algorithm: 'AES-GCM'
  iv_b64: string
  ciphertext_b64: string
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') {
    return null
  }

  const found = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))

  return found ? decodeURIComponent(found.split('=').slice(1).join('=')) : null
}

function toBase64(bytes: Uint8Array): string {
  if (typeof btoa !== 'function') {
    throw new Error('Secure auth bootstrap cache requires base64 browser APIs.')
  }

  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  return btoa(binary)
}

function fromBase64(value: string): ArrayBuffer {
  if (typeof atob !== 'function') {
    throw new Error('Secure auth bootstrap cache requires base64 browser APIs.')
  }

  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
}

async function deriveAuthBootstrapKey(userId: string): Promise<CryptoKey> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('Secure auth bootstrap cache requires Web Crypto support.')
  }

  const csrf = readCookie('hh_csrf')
  if (!csrf) {
    throw new Error('Secure auth bootstrap cache requires active session key material.')
  }

  const encoder = new TextEncoder()
  const baseKey = await crypto.subtle.importKey('raw', encoder.encode(csrf), { name: 'PBKDF2' }, false, ['deriveKey'])

  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: encoder.encode(`${PBKDF2_SALT_PREFIX}:${userId}`),
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export function isEncryptedAuthBootstrapPayload(payload: unknown): payload is EncryptedAuthBootstrapPayload {
  if (!payload || typeof payload !== 'object') {
    return false
  }

  const candidate = payload as Partial<EncryptedAuthBootstrapPayload>
  return (
    candidate.encrypted === true
    && candidate.version === AUTH_BOOTSTRAP_CACHE_VERSION
    && candidate.algorithm === 'AES-GCM'
    && typeof candidate.iv_b64 === 'string'
    && typeof candidate.ciphertext_b64 === 'string'
  )
}

export async function protectAuthBootstrapPayload(
  userId: string,
  payload: MePayload,
): Promise<EncryptedAuthBootstrapPayload> {
  const key = await deriveAuthBootstrapKey(userId)
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const plaintext = new TextEncoder().encode(JSON.stringify(payload))
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext)

  return {
    encrypted: true,
    version: AUTH_BOOTSTRAP_CACHE_VERSION,
    algorithm: 'AES-GCM',
    iv_b64: toBase64(iv),
    ciphertext_b64: toBase64(new Uint8Array(ciphertext)),
  }
}

export async function unprotectAuthBootstrapPayload(
  userId: string,
  payload: EncryptedAuthBootstrapPayload,
): Promise<MePayload> {
  const key = await deriveAuthBootstrapKey(userId)
  const iv = new Uint8Array(fromBase64(payload.iv_b64))
  const ciphertext = fromBase64(payload.ciphertext_b64)
  const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext)
  return JSON.parse(new TextDecoder().decode(decrypted)) as MePayload
}
