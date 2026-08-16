/**
 * Shared layout helpers — scale to real watch pixels (T-Rex 3 = 480×480).
 * Larger pad + type scale for readability on round bezels.
 */
import { getDeviceInfo } from '@zos/device'

export function screen() {
  let width = 480
  let height = 480
  try {
    const info = getDeviceInfo()
    width = info.width || width
    height = info.height || height
  } catch (_) {}
  // Was 6% — more inset so text clears the round edge
  const pad = Math.round(width * 0.09)
  const contentW = width - pad * 2
  return { width, height, pad, contentW, cx: Math.round(width / 2) }
}

export function yFrac(height, frac) {
  return Math.round(height * frac)
}

/** Type scale (fraction of screen width). */
export function typeSize(width, kind) {
  const map = {
    hero: 0.065,
    title: 0.055,
    body: 0.05,
    verse: 0.052,
    label: 0.042,
    meta: 0.038,
    caption: 0.034,
    button: 0.048,
    buttonSm: 0.042,
  }
  return Math.round(width * (map[kind] || map.body))
}
