/**
 * Keep the mini program alive while recording or sending over BLE.
 * Without this, Zepp OS dims the screen and exits the app ~10s later.
 */
import { setPageBrightTime, setWakeUpRelaunch } from '@zos/display'

export const CLOCK_BRIGHT_MS = 60_000
export const RECORD_BRIGHT_MS = (5 * 60 + 45) * 1000
export const SEND_BRIGHT_MS = 12 * 60 * 1000

export function keepAppOnWake() {
  try {
    setWakeUpRelaunch({ relaunch: true })
  } catch (_) {
    try {
      setWakeUpRelaunch(true)
    } catch (_) {}
  }
}

export function setBrightMs(ms) {
  try {
    setPageBrightTime({ brightTime: ms })
  } catch (_) {}
}

export function brightForClock() {
  setBrightMs(CLOCK_BRIGHT_MS)
}

export function brightForRecording() {
  setBrightMs(RECORD_BRIGHT_MS)
}

export function brightForSend() {
  setBrightMs(SEND_BRIGHT_MS)
}
