/**
 * Pure black-screen voice recorder — auto-start on open.
 * Needs device:os.mic (+ media/record) in app.json. API media @ 3.0+.
 */
import { createWidget, widget, align, prop } from '@zos/ui'
import { getDeviceInfo, getDiskInfo } from '@zos/device'
import { create, id, codec } from '@zos/media'
import { queryPermission, requestPermission } from '@zos/app'
import { Vibrator, VIBRATOR_SCENE_SHORT_MIDDLE, VIBRATOR_SCENE_SHORT_LIGHT } from '@zos/sensor'
import { log } from '@zos/utils'
import { back } from '@zos/router'

const logger = log.getLogger('calt-voice')
const MAX_SEC = 5 * 60
const MIN_FREE = 1024 * 1024 * 1024 // 1 GB
const MIC_PERMS = ['device:os.mic']

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

function showMsg(page, text) {
  try {
    page.msgW.setProperty(prop.TEXT, String(text || ' ').slice(0, 42))
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
    // Older firmwares may not gate mic this way — try anyway
    done(true)
  }
}

Page({
  state: {
    recorder: null,
    timer: null,
    elapsed: 0,
    recording: false,
    stopped: false,
    file: '',
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
      press_color: 0x000000,
      click_func: () => this.onTap(),
    })

    this.msgW = createWidget(widget.TEXT, {
      x: Math.round(width * 0.08),
      y: Math.round(height * 0.4),
      w: Math.round(width * 0.84),
      h: Math.round(height * 0.2),
      color: 0xff6666,
      text_size: Math.round(width * 0.04),
      align_h: align.CENTER_H,
      text: ' ',
    })

    try {
      const info = getDeviceInfo()
      if (info && info.hasMic === false) {
        showMsg(this, 'No mic on device')
        this.state.stopped = true
        return
      }
    } catch (_) {}

    const free = freeBytes()
    if (!(free >= MIN_FREE)) {
      const gb = free > 0 ? (free / MIN_FREE).toFixed(2) : '?'
      showMsg(this, `Need 1GB free (${gb})`)
      this.state.stopped = true
      return
    }

    // Defer so UI paints; then request mic and start
    ensureMicPermission((ok) => {
      if (!ok) {
        showMsg(this, 'Mic permission denied')
        this.state.stopped = true
        return
      }
      this.startRecording()
    })
  },

  onTap() {
    if (this.state.stopped) {
      try {
        back()
      } catch (_) {}
      return
    }
    if (this.state.recording) {
      this.finish('stopped')
    }
  },

  startRecording() {
    if (this.state.recording || this.state.stopped) return

    if (!id || id.RECORDER == null) {
      showMsg(this, 'Media API missing')
      this.state.stopped = true
      return
    }
    if (!codec || codec.OPUS == null) {
      showMsg(this, 'OPUS codec missing')
      this.state.stopped = true
      return
    }

    const file = `data://${stampName()}`
    this.state.file = file
    try {
      const recorder = create(id.RECORDER)
      if (!recorder || typeof recorder.setFormat !== 'function') {
        showMsg(this, 'Recorder create fail')
        this.state.stopped = true
        return
      }
      recorder.setFormat(codec.OPUS, { target_file: file })
      recorder.start()
      this.state.recorder = recorder
      this.state.recording = true
      this.state.elapsed = 0
      vibe('start')
      showMsg(this, ' ')

      this.state.timer = setInterval(() => {
        if (!this.state.recording) return
        this.state.elapsed += 1
        if (this.state.elapsed >= MAX_SEC) {
          this.finish('max')
        }
      }, 1000)
    } catch (e) {
      const msg = errText(e)
      logger.log(`start fail: ${msg}`)
      showMsg(this, `Mic: ${msg}`)
      this.state.stopped = true
    }
  },

  finish(reason) {
    if (this.state.stopped && !this.state.recording) return
    this.state.stopped = true
    this.state.recording = false
    if (this.state.timer) {
      clearInterval(this.state.timer)
      this.state.timer = null
    }
    try {
      if (this.state.recorder) this.state.recorder.stop()
    } catch (e) {
      logger.log(`stop ${e}`)
    }
    this.state.recorder = null
    vibe('end')
    showMsg(this, ' ')
    logger.log(`saved ${this.state.file} reason=${reason} sec=${this.state.elapsed}`)
  },

  onDestroy() {
    if (this.state.recording) {
      this.finish('leave')
    } else if (this.state.timer) {
      clearInterval(this.state.timer)
    }
  },
})
