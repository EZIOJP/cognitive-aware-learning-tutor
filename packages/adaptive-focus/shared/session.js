import { localStorage } from '@zos/storage'
import {
  DEFAULT_SETTINGS,
  MODE,
  MOTION,
  PHASE,
  SETTINGS_KEY,
  STORAGE_KEY,
} from './constants'
import { breakMinutesForPhase, classifyAuto, combinePhase } from './classifier'

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
  } catch (_) {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(patch) {
  const next = { ...loadSettings(), ...patch }
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(next))
  } catch (_) {}
  return next
}

export function emptySession() {
  return {
    mode: MODE.IDLE,
    phase: PHASE.NORMAL,
    motion: MOTION.UNKNOWN,
    auto: 'calm',
    running: false,
    paused: false,
    startedAt: 0,
    targetSec: 0,
    baseFocusSec: 0,
    extended: false,
    sessionCount: 0,
    baseStress: null,
    baseHr: null,
    prevStress: null,
    prevHr: null,
    lastSteps: null,
    zoneTicks: 0,
    fatigueTicks: 0,
    lastTickAt: 0,
    endReason: '',
    label: 'Ready',
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return emptySession()
    return { ...emptySession(), ...JSON.parse(raw) }
  } catch (_) {
    return emptySession()
  }
}

export function saveSession(session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch (_) {}
  return session
}

export function remainingSec(session, nowMs) {
  if (!session.targetSec) return 0
  if (!session.running) {
    // Paused: targetSec holds frozen remaining seconds
    if (session.paused) return Math.max(0, session.targetSec)
    if (!session.startedAt) return Math.max(0, session.targetSec)
  }
  if (!session.startedAt) return Math.max(0, session.targetSec)
  const elapsed = Math.floor(((nowMs || Date.now()) - session.startedAt) / 1000)
  return Math.max(0, session.targetSec - elapsed)
}

export function formatMmSs(sec) {
  const s = Math.max(0, Math.floor(sec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m < 10 ? '0' : ''}${m}:${r < 10 ? '0' : ''}${r}`
}

export function startFocus(settings) {
  const focusMin = settings.focusMin || 25
  const targetSec = focusMin * 60
  const s = {
    ...emptySession(),
    mode: MODE.FOCUS,
    running: true,
    startedAt: Date.now(),
    targetSec,
    baseFocusSec: targetSec,
    sessionCount: loadSession().sessionCount || 0,
    label: 'FOCUS',
    phase: PHASE.NORMAL,
  }
  return saveSession(s)
}

export function startBreak(settings, phase, sessionCount) {
  const mins = breakMinutesForPhase(phase, settings, sessionCount)
  const s = {
    ...emptySession(),
    mode: phase === PHASE.SPIKE ? MODE.BREATH : MODE.BREAK,
    running: true,
    startedAt: Date.now(),
    targetSec: mins * 60,
    sessionCount,
    phase,
    label: phase === PHASE.SPIKE ? 'BREATHE' : 'BREAK',
    endReason: phase,
  }
  return saveSession(s)
}

/**
 * Apply one sensor tick (from App Service or Device App).
 * Returns { session, events: string[] }
 */
export function applySensorTick(sample) {
  const settings = loadSettings()
  let session = loadSession()
  const events = []
  if (!session.running || session.mode === MODE.IDLE) {
    return { session, events }
  }

  const now = Date.now()
  const stepDelta =
    sample.steps != null && session.lastSteps != null
      ? Math.max(0, sample.steps - session.lastSteps)
      : 0
  if (sample.steps != null) session.lastSteps = sample.steps

  // Baseline from first few focus samples
  if (session.mode === MODE.FOCUS) {
    if (session.baseStress == null && sample.stress != null) session.baseStress = sample.stress
    if (session.baseHr == null && sample.hr != null) session.baseHr = sample.hr
  }

  const motion =
    sample.motion ||
    (stepDelta >= 8 ? MOTION.WALK : session.motion || MOTION.UNKNOWN)

  const auto = settings.lockClassic
    ? 'calm'
    : classifyAuto({
        stress: sample.stress,
        hr: sample.hr,
        restingHr: sample.restingHr,
        baseStress: session.baseStress,
        baseHr: session.baseHr,
        prevStress: session.prevStress,
        prevHr: session.prevHr,
        stepDelta,
        sensitivity: settings.sensitivity,
      })

  session.prevStress = sample.stress != null ? sample.stress : session.prevStress
  session.prevHr = sample.hr != null ? sample.hr : session.prevHr
  session.motion = motion
  session.auto = auto

  let phase = settings.lockClassic ? PHASE.NORMAL : combinePhase(motion, auto)
  session.phase = phase

  if (session.mode === MODE.FOCUS && !settings.lockClassic) {
    if (phase === PHASE.ZONE) {
      session.zoneTicks = (session.zoneTicks || 0) + 1
      session.fatigueTicks = 0
      // After ~3 calm ticks (~3 min), allow one extend
      if (!session.extended && session.zoneTicks >= 3) {
        const maxSec = (settings.maxFocusMin || 45) * 60
        const add = (settings.extendMin || 5) * 60
        if (session.targetSec + add <= maxSec) {
          session.targetSec += add
          session.extended = true
          session.label = `ZONE +${settings.extendMin || 5}m`
          events.push('extend')
        }
      } else if (session.extended) {
        session.label = `ZONE · ${motion}`
      } else {
        session.label = `FOCUS · ${motion}`
      }
    } else if (phase === PHASE.FATIGUE) {
      session.fatigueTicks = (session.fatigueTicks || 0) + 1
      session.label = 'FATIGUE'
      if (session.fatigueTicks >= 2) {
        session.running = false
        session.endReason = 'fatigue'
        events.push('fatigue_end')
      }
    } else if (phase === PHASE.SPIKE) {
      session.running = false
      session.endReason = 'spike'
      session.label = 'SPIKE'
      events.push('spike')
    } else {
      session.fatigueTicks = 0
      session.label = `FOCUS · ${motion}`
    }
  }

  const left = remainingSec(session, now)
  if (session.running && left <= 0) {
    session.running = false
    if (session.mode === MODE.FOCUS) {
      session.endReason = session.endReason || 'complete'
      events.push('focus_complete')
    } else {
      events.push('break_complete')
    }
  }

  session.lastTickAt = now
  saveSession(session)
  return { session, events }
}
