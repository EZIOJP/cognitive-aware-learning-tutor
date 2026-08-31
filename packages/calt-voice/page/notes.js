/**
 * Recording index + the byte helpers the transfer protocol needs.
 *
 * The index in localStorage is written the moment a recording stops, so a clip
 * is listed even if directory enumeration is unavailable on a given firmware.
 * Entries are always validated against statSync before being shown, so an
 * index that drifts from disk shows fewer files rather than phantom ones.
 */
import { localStorage } from '@zos/storage'
import { statSync, readdirSync } from '@zos/fs'

export const NOTES_INDEX_KEY = 'calt_voice_notes'
export const SENT_LOG_KEY = 'calt_voice_sent'
export const CHUNK_BYTES = 1024
export const FNV_INIT = 2166136261
const SENT_LOG_MAX = 12

const NAME_RE = /^voice_[0-9_]+\.opus$/

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

/** Base64 with padding — the hub decodes with validate=True. */
export function b64encode(bytes, len) {
  let out = ''
  let i = 0
  for (; i + 2 < len; i += 3) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2]
    out += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + B64[(n >> 6) & 63] + B64[n & 63]
  }
  const rem = len - i
  if (rem === 1) {
    const n = bytes[i] << 16
    out += `${B64[(n >> 18) & 63]}${B64[(n >> 12) & 63]}==`
  } else if (rem === 2) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8)
    out += `${B64[(n >> 18) & 63]}${B64[(n >> 12) & 63]}${B64[(n >> 6) & 63]}=`
  }
  return out
}

/** FNV-1a 32-bit. The hub reimplements this exactly; do not "optimize" it. */
export function fnvUpdate(h, bytes, len) {
  let acc = h
  for (let i = 0; i < len; i++) {
    acc ^= bytes[i]
    acc = Math.imul(acc, 16777619)
  }
  return acc
}

export function fnvHex(h) {
  return `h${(h >>> 0).toString(16)}`
}

function readIndex() {
  try {
    const raw = JSON.parse(localStorage.getItem(NOTES_INDEX_KEY) || '[]')
    return Array.isArray(raw) ? raw.map(String) : []
  } catch (_) {
    return []
  }
}

function writeIndex(names) {
  try {
    localStorage.setItem(NOTES_INDEX_KEY, JSON.stringify(names))
  } catch (_) {}
}

export function rememberNote(name) {
  if (!name) return
  const clean = String(name).replace(/^data:\/\//, '')
  const names = readIndex()
  if (names.indexOf(clean) < 0) {
    names.push(clean)
    writeIndex(names)
  }
}

export function forgetNote(name) {
  const names = readIndex().filter((n) => n !== name)
  writeIndex(names)
}

/**
 * Written only after a destination has re-hashed the clip and accepted it, so
 * this log is the watch's proof of where a deleted recording actually lives.
 */
export function recordSent(name, dest) {
  try {
    const raw = JSON.parse(localStorage.getItem(SENT_LOG_KEY) || '[]')
    const log = Array.isArray(raw) ? raw : []
    log.unshift({ name: String(name), dest: String(dest || '?'), at: Date.now() })
    localStorage.setItem(SENT_LOG_KEY, JSON.stringify(log.slice(0, SENT_LOG_MAX)))
  } catch (_) {}
}

export function sentLog() {
  try {
    const raw = JSON.parse(localStorage.getItem(SENT_LOG_KEY) || '[]')
    return Array.isArray(raw) ? raw : []
  } catch (_) {
    return []
  }
}

function discover() {
  // Directory listing is not available on every firmware; the index covers us
  // when it is not, so failures here are silent by design.
  const found = []
  const candidates = ['', '.', '/']
  for (let i = 0; i < candidates.length; i++) {
    try {
      const entries = readdirSync({ path: candidates[i] })
      if (entries && entries.length) {
        for (let j = 0; j < entries.length; j++) {
          const n = String(entries[j])
          if (NAME_RE.test(n) && found.indexOf(n) < 0) found.push(n)
        }
        break
      }
    } catch (_) {}
  }
  return found
}

/** Clips present on disk, newest first (the name embeds YYYYMMDD_HHMMSS). */
export function listNotes() {
  const seen = {}
  const out = []

  const consider = (name) => {
    if (!name || seen[name] || !NAME_RE.test(name)) return
    seen[name] = true
    try {
      const st = statSync({ path: name })
      if (!st || !st.size) return
      out.push({ name, size: st.size })
    } catch (_) {}
  }

  readIndex().forEach(consider)
  discover().forEach(consider)

  out.sort((a, b) => (a.name < b.name ? 1 : a.name > b.name ? -1 : 0))
  return out
}
