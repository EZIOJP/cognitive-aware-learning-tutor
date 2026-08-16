/**
 * Robust router params — Zepp may pass string/object to onInit, or via getParams().
 */
import { getParams } from '@zos/router'

export function normalizeParams(raw, fallback) {
  if (raw == null || raw === '') return fallback
  if (typeof raw === 'string') return raw
  if (typeof raw === 'object') {
    if (typeof raw.params === 'string') return raw.params
    if (raw.book != null) {
      return `${raw.book}|${raw.chapter != null ? raw.chapter : ''}|${raw.mode || ''}|${
        raw.page != null ? raw.page : 0
      }`
    }
    return String(raw)
  }
  return String(raw)
}

export function paramRaw(fallback) {
  try {
    return normalizeParams(getParams(), fallback)
  } catch (_) {
    return fallback
  }
}

export function splitParams(fallback, expected) {
  return splitParamsFrom(null, fallback, expected)
}

/** Prefer onInit(params); fall back to getParams() if needed. */
export function splitParamsFrom(routeParams, fallback, expected) {
  let raw = fallback
  if (routeParams != null && routeParams !== '') {
    raw = normalizeParams(routeParams, fallback)
  } else {
    raw = paramRaw(fallback)
  }
  const parts = String(raw).split('|')
  while (parts.length < expected) parts.push('')
  return parts
}
