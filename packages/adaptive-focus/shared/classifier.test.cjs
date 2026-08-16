/**
 * Node-side smoke test for classifier (no Zepp runtime).
 * Run: node shared/classifier.test.cjs
 */
const assert = require('assert')

// Minimal re-implementation mirror for CJS smoke (keep in sync with classifier.js)
const MOTION = { STILL: 'still', TYPING: 'typing', FIDGET: 'fidget', WALK: 'walk', UNKNOWN: 'unknown' }
const AUTO = { CALM: 'calm', ENGAGED: 'engaged', LOADED: 'loaded', SPIKE: 'spike' }
const PHASE = { NORMAL: 'normal', ZONE: 'zone', FATIGUE: 'fatigue', SPIKE: 'spike' }

function classifyMotion({ variance, zc, windowSec, stepDelta }) {
  const v = variance || 0
  const rate = windowSec > 0 ? (zc || 0) / windowSec : 0
  const steps = stepDelta || 0
  if (steps >= 8) return MOTION.WALK
  if (v < 0.015 && steps <= 1) return MOTION.STILL
  if (v < 0.12 && rate >= 1.2 && steps <= 2) return MOTION.TYPING
  if (v < 0.08 && steps <= 2) return MOTION.TYPING
  if (v >= 0.12 && steps <= 3) return MOTION.FIDGET
  if (steps >= 3) return MOTION.WALK
  return MOTION.UNKNOWN
}

function combinePhase(motion, auto) {
  if (auto === AUTO.SPIKE && motion !== MOTION.WALK) return PHASE.SPIKE
  if (motion === MOTION.WALK) return PHASE.NORMAL
  const desk = motion === MOTION.STILL || motion === MOTION.TYPING || motion === MOTION.UNKNOWN
  if (desk && (auto === AUTO.CALM || auto === AUTO.ENGAGED)) return PHASE.ZONE
  if (motion === MOTION.FIDGET && auto === AUTO.LOADED) return PHASE.FATIGUE
  if (auto === AUTO.LOADED) return PHASE.FATIGUE
  return PHASE.NORMAL
}

assert.strictEqual(classifyMotion({ variance: 0.01, zc: 0, windowSec: 8, stepDelta: 0 }), MOTION.STILL)
assert.strictEqual(classifyMotion({ variance: 0.05, zc: 20, windowSec: 8, stepDelta: 0 }), MOTION.TYPING)
assert.strictEqual(classifyMotion({ variance: 0.2, zc: 2, windowSec: 8, stepDelta: 12 }), MOTION.WALK)
assert.strictEqual(combinePhase(MOTION.TYPING, AUTO.CALM), PHASE.ZONE)
assert.strictEqual(combinePhase(MOTION.STILL, AUTO.SPIKE), PHASE.SPIKE)
assert.strictEqual(combinePhase(MOTION.FIDGET, AUTO.LOADED), PHASE.FATIGUE)
console.log('adaptive-focus classifier smoke OK')
