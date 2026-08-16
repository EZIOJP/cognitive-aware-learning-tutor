/**
 * Motion + autonomic classifier for Adaptive Focus.
 * Pure functions — usable from Device App and App Service.
 */

import { AUTO, MOTION, PHASE } from './constants'

/** Welford-lite: update running mean/M2 for accel magnitude samples */
export function pushVariance(state, x, y, z) {
  const mag = Math.sqrt(x * x + y * y + z * z)
  const n = (state.n || 0) + 1
  const delta = mag - (state.mean || 0)
  const mean = (state.mean || 0) + delta / n
  const M2 = (state.M2 || 0) + delta * (mag - mean)
  let zc = state.zc || 0
  if (state.prevMag != null && state.mean != null) {
    if ((state.prevMag - mean) * (mag - mean) < 0) zc += 1
  }
  return { n, mean, M2, zc, prevMag: mag, variance: n > 1 ? M2 / (n - 1) : 0 }
}

/**
 * Classify motion from accel variance + zero-cross rate + step delta.
 * Typing: low–mid variance, high zc, ~0 steps.
 * Walk: higher variance + step delta.
 */
export function classifyMotion({ variance, zc, windowSec, stepDelta }) {
  const v = variance || 0
  const rate = windowSec > 0 ? (zc || 0) / windowSec : 0
  const steps = stepDelta || 0

  if (steps >= 8) return MOTION.WALK
  if (v < 0.015 && steps <= 1) return MOTION.STILL
  // High-frequency micro-motion without steps ≈ typing / hand use
  if (v < 0.12 && rate >= 1.2 && steps <= 2) return MOTION.TYPING
  if (v < 0.08 && steps <= 2) return MOTION.TYPING
  if (v >= 0.12 && steps <= 3) return MOTION.FIDGET
  if (steps >= 3) return MOTION.WALK
  return MOTION.UNKNOWN
}

/**
 * Autonomic state vs session baselines.
 * @param {{ stress, hr, restingHr, baseStress, baseHr, prevStress, prevHr, sensitivity }} s
 */
export function classifyAuto(s) {
  const sens = s.sensitivity || 'normal'
  const spikeHr = sens === 'sensitive' ? 18 : sens === 'calm' ? 28 : 22
  const spikeStress = sens === 'sensitive' ? 12 : sens === 'calm' ? 20 : 15
  const loadStress = sens === 'sensitive' ? 8 : sens === 'calm' ? 14 : 10

  const stress = s.stress != null ? Number(s.stress) : null
  const hr = s.hr != null ? Number(s.hr) : null
  const baseS = s.baseStress != null ? Number(s.baseStress) : stress
  const baseH = s.baseHr != null ? Number(s.baseHr) : hr
  const rest = s.restingHr != null ? Number(s.restingHr) : baseH

  if (stress != null && s.prevStress != null && stress - s.prevStress >= spikeStress) {
    return AUTO.SPIKE
  }
  if (hr != null && s.prevHr != null && hr - s.prevHr >= spikeHr) {
    return AUTO.SPIKE
  }
  if (hr != null && rest != null && hr - rest >= spikeHr + 5 && (s.stepDelta || 0) < 3) {
    return AUTO.SPIKE
  }

  if (stress != null && baseS != null && stress - baseS >= loadStress) {
    return AUTO.LOADED
  }
  if (hr != null && baseH != null && hr - baseH >= 12) {
    return AUTO.LOADED
  }

  if (
    (stress == null || baseS == null || stress <= baseS + 3) &&
    (hr == null || rest == null || hr <= rest + 8)
  ) {
    return AUTO.CALM
  }
  return AUTO.ENGAGED
}

/**
 * Combine motion + auto → pomodoro phase.
 * Typing counts as focus-compatible (like still).
 */
export function combinePhase(motion, auto) {
  if (auto === AUTO.SPIKE && motion !== MOTION.WALK) return PHASE.SPIKE
  if (motion === MOTION.WALK) return PHASE.NORMAL
  const desk = motion === MOTION.STILL || motion === MOTION.TYPING || motion === MOTION.UNKNOWN
  if (desk && (auto === AUTO.CALM || auto === AUTO.ENGAGED)) return PHASE.ZONE
  if (motion === MOTION.FIDGET && auto === AUTO.LOADED) return PHASE.FATIGUE
  if (auto === AUTO.LOADED) return PHASE.FATIGUE
  return PHASE.NORMAL
}

export function breakMinutesForPhase(phase, settings, sessionCount) {
  const longEvery = settings.sessionsBeforeLong || 4
  if (phase === PHASE.SPIKE) return Math.max(settings.shortBreakMin || 5, 8)
  if (phase === PHASE.FATIGUE) return Math.max(settings.shortBreakMin || 5, 10)
  if (phase === PHASE.ZONE) return Math.min(settings.shortBreakMin || 5, 4)
  const n = sessionCount || 0
  if (n > 0 && n % longEvery === 0) return settings.longBreakMin || 15
  return settings.shortBreakMin || 5
}
