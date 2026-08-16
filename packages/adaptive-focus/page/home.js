/**
 * Home — Adaptive Focus timer UI + Accel typing classifier when raised.
 */
import { createWidget, widget, align, text_style, prop } from '@zos/ui'
import { push } from '@zos/router'
import { Vibrator, VIBRATOR_SCENE_SHORT_LIGHT, VIBRATOR_SCENE_SHORT_MIDDLE } from '@zos/sensor'
import { Accelerometer, FREQ_MODE_LOW, HeartRate, Stress, Step } from '@zos/sensor'
import { queryPermission, requestPermission } from '@zos/app'
import { start as startService, stop as stopService } from '@zos/app-service'
import { log as Logger } from '@zos/utils'
import {
  applySensorTick,
  formatMmSs,
  loadSession,
  loadSettings,
  remainingSec,
  saveSession,
  saveSettings,
  startBreak,
  startFocus,
} from '../shared/session'
import { classifyMotion, pushVariance } from '../shared/classifier'
import { MODE, PHASE } from '../shared/constants'

const logger = Logger.getLogger('af-home')
const SERVICE_FILE = 'app-service/focus'

function vibe(mode) {
  try {
    const v = new Vibrator()
    v.setMode(mode === 'mid' ? VIBRATOR_SCENE_SHORT_MIDDLE : VIBRATOR_SCENE_SHORT_LIGHT)
    v.start()
  } catch (_) {}
}

function ensureBgPermission(cb) {
  try {
    const result = queryPermission({ permissions: ['device:os.bg_service'] })
    const status = result && result[0]
    if (status === 2 /* granted approx */) {
      cb(true)
      return
    }
    requestPermission({
      permissions: ['device:os.bg_service'],
      callback(res) {
        cb(!!(res && res[0] === 2))
      },
    })
  } catch (e) {
    logger.log(`perm ${e}`)
    cb(false)
  }
}

function startBg() {
  ensureBgPermission((ok) => {
    if (!ok) {
      logger.log('bg permission denied — timer still works while app open')
      return
    }
    try {
      startService({ file: SERVICE_FILE, complete(r) {
        logger.log(`service start ${JSON.stringify(r)}`)
      } })
    } catch (e) {
      logger.log(`startService ${e}`)
    }
  })
}

function stopBg() {
  try {
    stopService({ file: SERVICE_FILE, complete() {} })
  } catch (_) {}
}

Page({
  state: {
    timer: null,
    accel: null,
    varState: null,
    accelWindowStart: 0,
    stepAtWindow: 0,
  },

  build() {
    const W = 480
    const pad = 24
    const contentW = W - pad * 2

    createWidget(widget.TEXT, {
      x: pad,
      y: 28,
      w: contentW,
      h: 36,
      color: 0xffffff,
      text_size: 28,
      align_h: align.CENTER_H,
      text_style: text_style.NONE,
      text: 'Adaptive Focus',
    })

    this.labelW = createWidget(widget.TEXT, {
      x: pad,
      y: 72,
      w: contentW,
      h: 40,
      color: 0x7dd3c0,
      text_size: 22,
      align_h: align.CENTER_H,
      text_style: text_style.NONE,
      text: 'Ready',
    })

    this.timeW = createWidget(widget.TEXT, {
      x: pad,
      y: 130,
      w: contentW,
      h: 90,
      color: 0xffffff,
      text_size: 72,
      align_h: align.CENTER_H,
      text_style: text_style.NONE,
      text: '25:00',
    })

    this.metaW = createWidget(widget.TEXT, {
      x: pad,
      y: 230,
      w: contentW,
      h: 70,
      color: 0xaaaaaa,
      text_size: 18,
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: 'Stress · HR · typing-aware',
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: 320,
      w: contentW,
      h: 56,
      radius: 28,
      normal_color: 0x1a9b8a,
      press_color: 0x147a6c,
      text: 'Start focus',
      text_size: 24,
      color: 0xffffff,
      click_func: () => this.onStart(),
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: 388,
      w: (contentW - 12) / 2,
      h: 48,
      radius: 24,
      normal_color: 0x333333,
      press_color: 0x444444,
      text: 'Pause',
      text_size: 20,
      color: 0xffffff,
      click_func: () => this.onPause(),
    })

    createWidget(widget.BUTTON, {
      x: pad + (contentW - 12) / 2 + 12,
      y: 388,
      w: (contentW - 12) / 2,
      h: 48,
      radius: 24,
      normal_color: 0x333333,
      press_color: 0x444444,
      text: 'Skip',
      text_size: 20,
      color: 0xffffff,
      click_func: () => this.onSkip(),
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: 444,
      w: (contentW - 12) / 2,
      h: 40,
      radius: 20,
      normal_color: 0x222222,
      press_color: 0x333333,
      text: 'Len 25/30',
      text_size: 16,
      color: 0xaaaaaa,
      click_func: () => {
        const s = loadSettings()
        const focusMin = s.focusMin >= 30 ? 20 : s.focusMin >= 25 ? 30 : 25
        saveSettings({ focusMin })
        this.refreshUi()
      },
    })

    createWidget(widget.BUTTON, {
      x: pad + (contentW - 12) / 2 + 12,
      y: 444,
      w: (contentW - 12) / 2,
      h: 40,
      radius: 20,
      normal_color: 0x222222,
      press_color: 0x333333,
      text: 'Classic',
      text_size: 16,
      color: 0xaaaaaa,
      click_func: () => {
        const s = loadSettings()
        saveSettings({ lockClassic: !s.lockClassic })
        this.refreshUi()
      },
    })

    this.refreshUi()
    this.startUiClock()
  },

  onShow() {
    this.refreshUi()
    this.startAccel()
  },

  onHide() {
    this.stopAccel()
  },

  onDestroy() {
    if (this.state.timer) clearInterval(this.state.timer)
    this.stopAccel()
  },

  startUiClock() {
    if (this.state.timer) clearInterval(this.state.timer)
    this.state.timer = setInterval(() => {
      this.tickLocal()
    }, 1000)
  },

  readSample(motion) {
    let stress = null
    let hr = null
    let restingHr = null
    let steps = null
    try {
      const st = new Stress()
      const c = st.getCurrent()
      stress = c && c.value != null ? c.value : null
    } catch (_) {}
    try {
      const h = new HeartRate()
      hr = h.getLast()
      restingHr = h.getResting && h.getResting()
    } catch (_) {}
    try {
      steps = new Step().getCurrent()
    } catch (_) {}
    return { stress, hr, restingHr, steps, motion }
  },

  tickLocal() {
    const session = loadSession()
    if (!session.running) {
      this.refreshUi()
      return
    }
    // Accel window (~8s) for typing vs walk when UI awake
    let motion = session.motion
    if (this.state.varState && this.state.accelWindowStart) {
      const win = (Date.now() - this.state.accelWindowStart) / 1000
      if (win >= 6) {
        const steps = (() => {
          try {
            return new Step().getCurrent()
          } catch (_) {
            return this.state.stepAtWindow
          }
        })()
        motion = classifyMotion({
          variance: this.state.varState.variance,
          zc: this.state.varState.zc,
          windowSec: win,
          stepDelta: Math.max(0, (steps || 0) - (this.state.stepAtWindow || 0)),
        })
        this.state.varState = null
        this.state.accelWindowStart = Date.now()
        this.state.stepAtWindow = steps || 0
      }
    }

    const { session: next, events } = applySensorTick(this.readSample(motion))
    this.handleEvents(events, next)
    this.refreshUi()
  },

  handleEvents(events, session) {
    if (!events || !events.length) return
    const settings = loadSettings()
    if (events.indexOf('extend') >= 0) vibe('light')
    if (events.indexOf('spike') >= 0) {
      vibe('mid')
      startBreak(settings, PHASE.SPIKE, session.sessionCount || 0)
      push({ url: 'page/end' })
      return
    }
    if (events.indexOf('fatigue_end') >= 0) {
      const count = (session.sessionCount || 0) + 1
      const b = startBreak(settings, PHASE.FATIGUE, count)
      b.sessionCount = count
      saveSession(b)
      push({ url: 'page/end' })
      return
    }
    if (events.indexOf('focus_complete') >= 0) {
      const count = (session.sessionCount || 0) + 1
      const b = startBreak(settings, session.phase || PHASE.NORMAL, count)
      b.sessionCount = count
      saveSession(b)
      vibe('light')
      push({ url: 'page/end' })
      return
    }
    if (events.indexOf('break_complete') >= 0) {
      session.mode = MODE.IDLE
      session.running = false
      session.label = 'Ready'
      saveSession(session)
      stopBg()
    }
  },

  startAccel() {
    this.stopAccel()
    try {
      const accel = new Accelerometer()
      this.state.accel = accel
      this.state.varState = { n: 0, mean: 0, M2: 0, zc: 0 }
      this.state.accelWindowStart = Date.now()
      try {
        this.state.stepAtWindow = new Step().getCurrent()
      } catch (_) {
        this.state.stepAtWindow = 0
      }
      accel.onChange(() => {
        try {
          const { x, y, z } = accel.getCurrent()
          this.state.varState = pushVariance(this.state.varState || {}, x, y, z)
        } catch (_) {}
      })
      if (typeof accel.setFreqMode === 'function') {
        accel.setFreqMode(FREQ_MODE_LOW)
      }
      accel.start()
    } catch (e) {
      logger.log(`accel ${e}`)
    }
  },

  stopAccel() {
    try {
      if (this.state.accel) {
        this.state.accel.stop && this.state.accel.stop()
        this.state.accel.offChange && this.state.accel.offChange()
      }
    } catch (_) {}
    this.state.accel = null
  },

  onStart() {
    const settings = loadSettings()
    const session = loadSession()
    if (session.running && session.mode === MODE.FOCUS) {
      session.running = true
      saveSession(session)
      startBg()
      this.refreshUi()
      return
    }
    startFocus(settings)
    vibe('light')
    startBg()
    this.startAccel()
    this.refreshUi()
  },

  onPause() {
    const session = loadSession()
    if (!session.running) {
      if (session.mode !== MODE.IDLE && session.targetSec > 0) {
        // resume from frozen remaining in targetSec
        const left = session.paused ? session.targetSec : remainingSec(session)
        session.startedAt = Date.now()
        session.targetSec = left
        session.paused = false
        session.running = true
        saveSession(session)
        startBg()
      }
      this.refreshUi()
      return
    }
    const left = remainingSec(session)
    session.running = false
    session.paused = true
    session.targetSec = left
    session.startedAt = Date.now()
    saveSession(session)
    this.refreshUi()
  },

  onSkip() {
    const session = loadSession()
    const settings = loadSettings()
    if (session.mode === MODE.FOCUS) {
      const count = (session.sessionCount || 0) + 1
      const b = startBreak(settings, session.phase || PHASE.NORMAL, count)
      b.sessionCount = count
      saveSession(b)
      push({ url: 'page/end' })
      return
    }
    session.mode = MODE.IDLE
    session.running = false
    session.label = 'Ready'
    saveSession(session)
    stopBg()
    this.refreshUi()
  },

  refreshUi() {
    const session = loadSession()
    const settings = loadSettings()
    const left =
      session.running || session.mode !== MODE.IDLE
        ? remainingSec(session)
        : (settings.focusMin || 25) * 60
    if (this.timeW) this.timeW.setProperty(prop.TEXT, formatMmSs(left))
    if (this.labelW) {
      this.labelW.setProperty(prop.TEXT, session.label || 'Ready')
      const color =
        session.phase === PHASE.ZONE
          ? 0x7dd3c0
          : session.phase === PHASE.FATIGUE
            ? 0xf0c674
            : session.phase === PHASE.SPIKE
              ? 0xe06c75
              : 0xffffff
      this.labelW.setProperty(prop.COLOR, color)
    }
    if (this.metaW) {
      const lock = settings.lockClassic ? ' · classic' : ''
      this.metaW.setProperty(
        prop.TEXT,
        `${session.mode || 'idle'} · ${session.motion || '—'} · ${session.auto || '—'}${lock}\n` +
          `sessions ${session.sessionCount || 0}${session.extended ? ' · extended' : ''}`,
      )
    }
  },
})
