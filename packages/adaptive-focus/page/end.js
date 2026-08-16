/**
 * End / break coach screen.
 */
import { createWidget, widget, align, text_style, prop } from '@zos/ui'
import { replace } from '@zos/router'
import { Vibrator, VIBRATOR_SCENE_SHORT_MIDDLE, VIBRATOR_SCENE_DURATION } from '@zos/sensor'
import {
  formatMmSs,
  loadSession,
  loadSettings,
  remainingSec,
  saveSession,
  startFocus,
} from '../shared/session'
import { MODE, PHASE } from '../shared/constants'
import { start as startService } from '@zos/app-service'

const SERVICE_FILE = 'app-service/focus'

function breathPulse() {
  try {
    const v = new Vibrator()
    v.setMode(VIBRATOR_SCENE_SHORT_MIDDLE)
    v.start()
    setTimeout(() => {
      try {
        v.setMode(VIBRATOR_SCENE_DURATION)
        v.start()
      } catch (_) {}
    }, 4000)
  } catch (_) {}
}

Page({
  state: { timer: null },

  build() {
    const pad = 24
    const contentW = 480 - pad * 2
    const session = loadSession()

    createWidget(widget.TEXT, {
      x: pad,
      y: 36,
      w: contentW,
      h: 40,
      color: 0xffffff,
      text_size: 26,
      align_h: align.CENTER_H,
      text: session.mode === MODE.BREATH ? 'Breathe' : 'Smart break',
    })

    this.timeW = createWidget(widget.TEXT, {
      x: pad,
      y: 100,
      w: contentW,
      h: 80,
      color: 0x7dd3c0,
      text_size: 64,
      align_h: align.CENTER_H,
      text: formatMmSs(remainingSec(session)),
    })

    const tip =
      session.phase === PHASE.SPIKE
        ? 'Inhale 4 · hold 7 · exhale 8\nWrist will pulse as a guide'
        : session.phase === PHASE.FATIGUE
          ? 'Eyes away from screen\nStand or stretch slowly'
          : session.phase === PHASE.ZONE
            ? 'Short reset — you were in the zone'
            : 'Rest, then another focus block'

    createWidget(widget.TEXT, {
      x: pad,
      y: 200,
      w: contentW,
      h: 100,
      color: 0xcccccc,
      text_size: 20,
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: tip,
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: 330,
      w: contentW,
      h: 56,
      radius: 28,
      normal_color: 0x1a9b8a,
      press_color: 0x147a6c,
      text: 'Next focus',
      text_size: 24,
      color: 0xffffff,
      click_func: () => {
        const settings = loadSettings()
        startFocus(settings)
        try {
          startService({ file: SERVICE_FILE, complete() {} })
        } catch (_) {}
        replace({ url: 'page/home' })
      },
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: 400,
      w: contentW,
      h: 48,
      radius: 24,
      normal_color: 0x333333,
      press_color: 0x444444,
      text: 'Done',
      text_size: 20,
      color: 0xffffff,
      click_func: () => {
        const s = loadSession()
        s.mode = MODE.IDLE
        s.running = false
        s.label = 'Ready'
        saveSession(s)
        replace({ url: 'page/home' })
      },
    })

    if (session.mode === MODE.BREATH || session.phase === PHASE.SPIKE) {
      breathPulse()
    }

    this.state.timer = setInterval(() => {
      const s = loadSession()
      if (this.timeW) this.timeW.setProperty(prop.TEXT, formatMmSs(remainingSec(s)))
      if (!s.running || remainingSec(s) <= 0) {
        // auto ready
      }
    }, 1000)
  },

  onDestroy() {
    if (this.state.timer) clearInterval(this.state.timer)
  },
})
