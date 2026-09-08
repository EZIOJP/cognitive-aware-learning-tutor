/**
 * Clock-first voice recorder — shows live time on open; tap to record/stop.
 * Needs device:os.mic (+ media/record) in app.json. API media @ 3.0+.
 */
import { createWidget, widget, align, prop } from '@zos/ui'
import { getDeviceInfo, getDiskInfo } from '@zos/device'
import { create, id, codec } from '@zos/media'
import { queryPermission, requestPermission } from '@zos/app'
import { Vibrator, VIBRATOR_SCENE_SHORT_MIDDLE, VIBRATOR_SCENE_SHORT_LIGHT } from '@zos/sensor'
import { log } from '@zos/utils'
import { back, push } from '@zos/router'
import { onGesture, offGesture, GESTURE_LEFT } from '@zos/interaction'
import { rememberNote } from './notes'
import {
  brightForClock,
  brightForRecording,
  keepAppOnWake,
} from '../shared/displayKeep'
import {
  readRecordGain,
  writeRecordGain,
  recorderFormatOptions,
  primeRecorder,
} from '../shared/recordingConfig'
import { hubFromSide } from '../shared/sidePayload'

const logger = log.getLogger('calt-voice')
const MAX_SEC = 5 * 60
const MIN_FREE = 1024 * 1024 * 1024 // 1 GB
const MIC_PERMS = ['device:os.mic']
const TICK_MS = 250
const CLOCK_MS = 1000

// Dim red steps while recording — one cycle = PULSE.length * TICK_MS = 2s.
const PULSE = [0x1c0000, 0x330000, 0x5c0000, 0x8c0000, 0xb31111, 0x8c0000, 0x5c0000, 0x330000]
const DOT_OFF = 0x000000

function vibe(kind) {
  try {
    const v = new Vibrator()
    v.setMode(kind === 'end' ? VIBRATOR_SCENE_SHORT_MIDDLE : VIBRATOR_SCENE_SHORT_LIGHT)
    v.start()
  } catch (e) {
    logger.log(`vibe ${e}`)
  }
}

function pad2(n) {
  return n < 10 ? `0${n}` : `${n}`
}

function fmtElapsed(sec) {
  return `${pad2(Math.floor(sec / 60))}:${pad2(sec % 60)}`
}

function fmtClock(d) {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

function fmtDate(d) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  return `${days[d.getDay()]} ${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`
}

function stampName() {
  const d = new Date()
  return (
    `voice_${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}` +
    `_${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}.opus`
  )
}

function freeBytes() {
  try {
    const info = getDiskInfo()
    return Number(info && info.free) || 0
  } catch (_) {
    return 0
  }
}

function errText(e) {
  if (e == null) return 'unknown'
  if (typeof e === 'string') return e
  try {
    if (e.message) return String(e.message)
    return String(e)
  } catch (_) {
    return 'error'
  }
}

function showMsg(page, text, color) {
  try {
    page.msgW.setProperty(prop.MORE, {
      text: String(text || ' ').slice(0, 42),
      color: color || 0x666666,
    })
  } catch (_) {}
}

function ensureMicPermission(done) {
  try {
    const q = queryPermission({ permissions: MIC_PERMS })
    const status = q && q[0]
    if (status === 2) {
      done(true)
      return
    }
    requestPermission({
      permissions: MIC_PERMS,
      callback(res) {
        done(!!(res && res[0] === 2))
      },
    })
  } catch (e) {
    logger.log(`perm ${e}`)
    done(true)
  }
}

Page({
  state: {
    recorder: null,
    recTimer: null,
    clockTimer: null,
    elapsed: 0,
    startedAt: 0,
    frame: 0,
    recording: false,
    stopped: false,
    ready: false,
    file: '',
  },

  onInit() {
    onGesture((event) => {
      if (event === GESTURE_LEFT) {
        if (!this.state.recording) push({ url: 'page/files' })
        return true
      }
      return false
    })
  },

  build() {
    let width = 480
    let height = 480
    try {
      const info = getDeviceInfo()
      width = info.width || width
      height = info.height || height
    } catch (_) {}

    createWidget(widget.FILL_RECT, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      color: 0x000000,
    })

    createWidget(widget.BUTTON, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      text: '',
      text_size: 1,
      normal_color: 0x000000,
      press_color: 0x050505,
      click_func: () => this.onTap(),
    })

    this.dateW = createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.22),
      w: width,
      h: Math.round(height * 0.07),
      color: 0x888888,
      text_size: Math.round(width * 0.045),
      align_h: align.CENTER_H,
      text: fmtDate(new Date()),
    })

    this.clockW = createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.3),
      w: width,
      h: Math.round(height * 0.18),
      color: 0xffffff,
      text_size: Math.round(width * 0.16),
      align_h: align.CENTER_H,
      text: fmtClock(new Date()),
    })

    this.msgW = createWidget(widget.TEXT, {
      x: Math.round(width * 0.08),
      y: Math.round(height * 0.52),
      w: Math.round(width * 0.84),
      h: Math.round(height * 0.1),
      color: 0x666666,
      text_size: Math.round(width * 0.038),
      align_h: align.CENTER_H,
      text: 'Tap to record',
    })

    this.dotGeom = {
      center_x: Math.round(width / 2),
      center_y: Math.round(height * 0.66),
      radius: Math.round(width * 0.022),
    }
    this.dotW = createWidget(widget.CIRCLE, { ...this.dotGeom, color: DOT_OFF })

    this.timeW = createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.72),
      w: width,
      h: Math.round(height * 0.08),
      color: 0x3a3a3a,
      text_size: Math.round(width * 0.05),
      align_h: align.CENTER_H,
      text: '',
    })

    this.hintW = createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.82),
      w: width,
      h: Math.round(height * 0.06),
      color: 0x444444,
      text_size: Math.round(width * 0.032),
      align_h: align.CENTER_H,
      text: '← files',
    })

    try {
      const info = getDeviceInfo()
      if (info && info.hasMic === false) {
        showMsg(this, 'No mic on device', 0xff6666)
        this.state.stopped = true
        return
      }
    } catch (_) {}

    const free = freeBytes()
    if (!(free >= MIN_FREE)) {
      const gb = free > 0 ? (free / MIN_FREE).toFixed(2) : '?'
      showMsg(this, `Need 1GB free (${gb})`, 0xff6666)
      this.state.stopped = true
      return
    }

    this.startClock()
    keepAppOnWake()
    brightForClock()
    ensureMicPermission((ok) => {
      this.state.ready = ok
      if (!ok) showMsg(this, 'Mic permission denied', 0xff6666)
      else this.syncGainFromPhone()
    })
  },

  syncGainFromPhone() {
    const app = getApp()
    const { messageBuilder: mb } = (app && app.globalData) || {}
    if (!mb) return
    mb.request({ method: 'VN_GET_CONFIG' })
      .then((res) => {
        const { body } = hubFromSide(res)
        if (body && body.gain != null) {
          const gain = writeRecordGain(body.gain)
          if (!this.state.recording) {
            showMsg(this, `Voice gain ${gain.toFixed(1)}× · tap to record`, 0x666666)
          }
        }
      })
      .catch(() => {})
  },

  startClock() {
    let brightTick = 0
    const tick = () => {
      const d = new Date()
      try {
        this.clockW.setProperty(prop.TEXT, fmtClock(d))
        this.dateW.setProperty(prop.TEXT, fmtDate(d))
      } catch (_) {}
      if (!this.state.recording) {
        brightTick += 1
        if (brightTick >= 25) {
          brightTick = 0
          brightForClock()
        }
      }
    }
    tick()
    this.state.clockTimer = setInterval(tick, CLOCK_MS)
  },

  stopClock() {
    if (this.state.clockTimer) {
      clearInterval(this.state.clockTimer)
      this.state.clockTimer = null
    }
  },

  onTap() {
    if (this.state.stopped && !this.state.recording) {
      // After save — stay on clock; tap does nothing suspicious
      return
    }
    if (this.state.recording) {
      this.finish('stopped')
      return
    }
    if (!this.state.ready) {
      ensureMicPermission((ok) => {
        this.state.ready = ok
        if (ok) this.startRecording()
        else showMsg(this, 'Mic permission denied', 0xff6666)
      })
      return
    }
    this.startRecording()
  },

  startRecording() {
    if (this.state.recording || this.state.stopped) return

    if (!id || id.RECORDER == null) {
      showMsg(this, 'Media API missing', 0xff6666)
      this.state.stopped = true
      return
    }
    if (!codec || codec.OPUS == null) {
      showMsg(this, 'OPUS codec missing', 0xff6666)
      this.state.stopped = true
      return
    }

    const file = `data://${stampName()}`
    this.state.file = file
    const gain = readRecordGain()
    try {
      const recorder = create(id.RECORDER)
      if (!recorder || typeof recorder.setFormat !== 'function') {
        showMsg(this, 'Recorder create fail', 0xff6666)
        this.state.stopped = true
        return
      }
      primeRecorder(recorder, gain)
      recorder.setFormat(codec.OPUS, recorderFormatOptions(file, gain))
      recorder.start()
      this.state.recorder = recorder
      this.state.recording = true
      this.state.elapsed = 0
      this.state.startedAt = Date.now()
      this.state.frame = 0
      vibe('start')
      showMsg(this, `Recording ${gain.toFixed(1)}× — tap to stop`, 0xff6666)
      brightForRecording()

      this.state.recTimer = setInterval(() => this.recTick(), TICK_MS)
      this.recTick()
    } catch (e) {
      const msg = errText(e)
      logger.log(`start fail: ${msg}`)
      showMsg(this, `Mic: ${msg}`, 0xff6666)
      this.state.stopped = true
    }
  },

  recTick() {
    if (!this.state.recording) return

    const sec = Math.floor((Date.now() - this.state.startedAt) / 1000)
    if (sec !== this.state.elapsed) {
      this.state.elapsed = sec
      try {
        this.timeW.setProperty(prop.TEXT, fmtElapsed(sec))
      } catch (_) {}
      brightForRecording()
    }

    this.state.frame = (this.state.frame + 1) % PULSE.length
    try {
      this.dotW.setProperty(prop.MORE, {
        ...this.dotGeom,
        color: PULSE[this.state.frame],
      })
    } catch (_) {}

    if (sec >= MAX_SEC) this.finish('max')
  },

  finish(reason) {
    if (!this.state.recording && this.state.stopped) return
    this.state.stopped = true
    this.state.recording = false
    if (this.state.recTimer) {
      clearInterval(this.state.recTimer)
      this.state.recTimer = null
    }
    try {
      this.dotW.setProperty(prop.MORE, { ...this.dotGeom, color: DOT_OFF })
    } catch (_) {}
    try {
      if (this.state.recorder) this.state.recorder.stop()
    } catch (e) {
      logger.log(`stop ${e}`)
    }
    this.state.recorder = null
    vibe('end')

    rememberNote(this.state.file)

    try {
      this.timeW.setProperty(prop.TEXT, `Saved ${fmtElapsed(this.state.elapsed)}`)
    } catch (_) {}
    showMsg(this, 'Saved · swipe ← to send', 0x88c0bb)
    brightForClock()
    logger.log(`saved ${this.state.file} reason=${reason} sec=${this.state.elapsed}`)
  },

  onDestroy() {
    if (this.state.recording) {
      this.finish('leave')
    } else if (this.state.recTimer) {
      clearInterval(this.state.recTimer)
    }
    this.stopClock()
    try {
      offGesture()
    } catch (_) {}
  },
})
