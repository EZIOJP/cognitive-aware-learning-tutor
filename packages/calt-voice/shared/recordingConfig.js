/**
 * Recording gain for human voice clips.
 *
 * Zepp OS @zos/media Recorder only documents target_file in setFormat — no official
 * mic gain knob. We still pass common optional keys some firmware builds accept,
 * and the PC hub applies digital gain after reassembly when opus decode is available.
 */
import { localStorage } from '@zos/storage'

export const GAIN_STORAGE_KEY = 'calt_voice_gain'
export const DEFAULT_RECORD_GAIN = 2.5
export const MIN_RECORD_GAIN = 1.0
export const MAX_RECORD_GAIN = 4.0

export function clampGain(raw) {
  const n = Number(raw)
  if (!Number.isFinite(n)) return DEFAULT_RECORD_GAIN
  return Math.min(MAX_RECORD_GAIN, Math.max(MIN_RECORD_GAIN, n))
}

export function readRecordGain() {
  try {
    const raw = localStorage.getItem(GAIN_STORAGE_KEY)
    if (raw !== undefined && raw !== null && raw !== '') return clampGain(raw)
  } catch (_) {}
  return DEFAULT_RECORD_GAIN
}

export function writeRecordGain(value) {
  const gain = clampGain(value)
  try {
    localStorage.setItem(GAIN_STORAGE_KEY, String(gain))
  } catch (_) {}
  return gain
}

/** Options passed to recorder.setFormat — includes undocumented keys to try. */
export function recorderFormatOptions(targetFile, gain) {
  const g = clampGain(gain)
  return {
    target_file: targetFile,
    gain: g,
    volume: g,
    mic_gain: g,
  }
}

/** Best-effort pre-roll tweaks before recorder.start(). */
export function primeRecorder(recorder, gain) {
  const g = clampGain(gain)
  try {
    if (recorder && typeof recorder.setVolume === 'function') {
      recorder.setVolume(100)
    }
  } catch (_) {}
  return g
}
