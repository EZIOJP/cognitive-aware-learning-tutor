/**
 * Files — list recordings and send one to a receiver over BLE.
 *
 * Transfer is deliberately conservative rather than fast:
 *   1. hash the whole clip locally,
 *   2. VN_BEGIN declares name/size/chunking/hash and returns chunks the
 *      receiver already holds, so an interrupted send resumes instead of
 *      restarting, plus the destination index that answered,
 *   3. every chunk carries its own hash and a fixed index, so a resend
 *      overwrites the same offset,
 *   4. VN_FINISH re-hashes the reassembled file at the destination.
 *
 * The local file is deleted only after step 4 succeeds. An interrupted
 * transfer therefore costs airtime, never the recording.
 *
 * Everything listed here is on the watch ONLY — the phone cannot hold clips
 * (see README: the Zepp side service has no filesystem read API), so a clip
 * either sits here or has been verified by a receiver and deleted.
 */
import { createWidget, widget, align, prop } from '@zos/ui'
import { getDeviceInfo } from '@zos/device'
import { openSync, readSync, closeSync, rmSync, O_RDONLY } from '@zos/fs'
import { log } from '@zos/utils'
import {
  listNotes,
  forgetNote,
  recordSent,
  sentLog,
  b64encode,
  fnvUpdate,
  fnvHex,
  CHUNK_BYTES,
  FNV_INIT,
} from './notes'
import { hubFromSide } from '../shared/sidePayload'

const logger = log.getLogger('calt-voice-files')
const MAX_ROWS = 4

const COLOR_OK = 0x88c0bb
const COLOR_BUSY = 0xf0c674
const COLOR_ERR = 0xff6666
const COLOR_MUTED = 0x9aa0a6

function errText(e) {
  if (e == null) return 'unknown'
  if (typeof e === 'string') return e
  try {
    return e.message ? String(e.message) : String(e)
  } catch (_) {
    return 'error'
  }
}

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  return `${Math.max(1, Math.round(bytes / 1024))}KB`
}

function fmtName(name) {
  // voice_20260831_141203.opus -> 08-31 14:12
  const m = /^voice_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/.exec(name)
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : name
}

/** One streaming pass, so a long clip never has to fit in memory at once. */
function hashFile(name, size) {
  const fd = openSync({ path: name, flag: O_RDONLY })
  const buf = new ArrayBuffer(CHUNK_BYTES)
  const view = new Uint8Array(buf)
  let h = FNV_INIT
  let pos = 0
  try {
    while (pos < size) {
      const len = Math.min(CHUNK_BYTES, size - pos)
      const got = readSync({ fd, buffer: buf, options: { offset: 0, length: len, position: pos } })
      if (got !== len) throw new Error(`short read at ${pos}`)
      h = fnvUpdate(h, view, len)
      pos += len
    }
  } finally {
    try {
      closeSync({ fd })
    } catch (_) {}
  }
  return fnvHex(h)
}

Page({
  state: {
    busy: false,
    notes: [],
  },

  build() {
    let width = 480
    let height = 480
    try {
      const info = getDeviceInfo()
      width = info.width || width
      height = info.height || height
    } catch (_) {}
    this.width = width

    createWidget(widget.FILL_RECT, { x: 0, y: 0, w: width, h: height, color: 0x000000 })

    createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.07),
      w: width,
      h: Math.round(height * 0.08),
      color: 0xffffff,
      text_size: Math.round(width * 0.055),
      align_h: align.CENTER_H,
      text: 'Voice files',
    })

    this.statusW = createWidget(widget.TEXT, {
      x: Math.round(width * 0.08),
      y: Math.round(height * 0.17),
      w: Math.round(width * 0.84),
      h: Math.round(height * 0.12),
      color: COLOR_MUTED,
      text_size: Math.round(width * 0.04),
      align_h: align.CENTER_H,
      text_style: 2,
      text: 'Tap a clip to send',
    })

    this.rowW = []
    const rowH = Math.round(height * 0.11)
    for (let i = 0; i < MAX_ROWS; i++) {
      this.rowW.push(
        createWidget(widget.BUTTON, {
          x: Math.round(width * 0.1),
          y: Math.round(height * 0.32) + i * (rowH + 6),
          w: Math.round(width * 0.8),
          h: rowH,
          text: '',
          text_size: Math.round(width * 0.042),
          normal_color: 0x1c1c20,
          press_color: 0x2f2f36,
          radius: Math.round(rowH / 2),
          click_func: () => this.onRow(i),
        }),
      )
    }

    this.moreW = createWidget(widget.TEXT, {
      x: 0,
      y: Math.round(height * 0.32) + MAX_ROWS * (rowH + 6) + 4,
      w: width,
      h: Math.round(height * 0.06),
      color: COLOR_MUTED,
      text_size: Math.round(width * 0.035),
      align_h: align.CENTER_H,
      text: '',
    })

    this.render()
    if (this.state.notes.length) this.probe()
  },

  setStatus(text, color) {
    try {
      this.statusW.setProperty(prop.MORE, { text: String(text || ''), color: color || COLOR_MUTED })
    } catch (_) {}
  },

  render() {
    const notes = listNotes()
    this.state.notes = notes

    for (let i = 0; i < MAX_ROWS; i++) {
      const note = notes[i]
      try {
        this.rowW[i].setProperty(
          prop.TEXT,
          note ? `${fmtName(note.name)}   ${fmtSize(note.size)}` : '',
        )
      } catch (_) {}
    }

    const older = notes.length > MAX_ROWS ? `+${notes.length - MAX_ROWS} older · ` : ''
    const last = sentLog()[0]
    try {
      this.moreW.setProperty(
        prop.TEXT,
        last ? `${older}last → ${last.dest || 'receiver'}` : older.replace(/ · $/, ''),
      )
    } catch (_) {}

    if (!notes.length) {
      this.setStatus('Nothing on watch', COLOR_OK)
      return
    }
    // "on watch" is the whole truth: the phone cannot store clips.
    let bytes = 0
    notes.forEach((n) => {
      bytes += n.size
    })
    this.setStatus(`${notes.length} on watch · ${fmtSize(bytes)}`, COLOR_MUTED)
  },

  /**
   * Tells the user whether a send can succeed at all before they commit to a
   * multi-minute transfer. Read-only: it never moves bytes.
   */
  probe() {
    const self = this
    const app = getApp()
    const { messageBuilder: mb } = (app && app.globalData) || {}
    if (!mb) return
    mb.request({ method: 'VN_PING' })
      .then((res) => {
        const { env } = hubFromSide(res)
        if (self.state.busy) return
        if (env.ok) self.setStatus(`Receiver up: ${env.host || 'ok'}`, COLOR_OK)
        else self.setStatus(`No receiver: ${env.error || 'offline'}`, COLOR_ERR)
      })
      .catch(() => {})
  },

  onRow(i) {
    if (this.state.busy) {
      this.setStatus('Transfer in progress', COLOR_BUSY)
      return
    }
    const note = this.state.notes[i]
    if (note) this.send(note)
  },

  send(note) {
    const self = this
    const app = getApp()
    const { messageBuilder: mb } = (app && app.globalData) || {}
    if (!mb) {
      this.setStatus('No phone link', COLOR_ERR)
      return
    }

    this.state.busy = true
    this.setStatus(`Hashing ${fmtSize(note.size)}…`, COLOR_BUSY)

    let sha
    try {
      sha = hashFile(note.name, note.size)
    } catch (e) {
      this.state.busy = false
      this.setStatus(`Read failed: ${errText(e)}`, COLOR_ERR)
      return
    }

    const total = Math.ceil(note.size / CHUNK_BYTES)
    const buf = new ArrayBuffer(CHUNK_BYTES)
    const view = new Uint8Array(buf)
    let fd = -1

    const closeFd = () => {
      try {
        if (fd >= 0) closeSync({ fd })
      } catch (_) {}
      fd = -1
    }

    const fail = (msg) => {
      closeFd()
      self.state.busy = false
      self.setStatus(msg, COLOR_ERR)
      logger.log(`send fail: ${msg}`)
    }

    /**
     * Safe only here: the destination holds the bytes and has re-hashed them.
     * `host` is recorded first so the watch keeps proof of where it went.
     */
    const dropLocal = (host) => {
      closeFd()
      recordSent(note.name, host)
      try {
        rmSync({ path: note.name })
      } catch (e) {
        logger.log(`rm ${errText(e)}`)
      }
      forgetNote(note.name)
      self.state.busy = false
      self.setStatus(`Stored on ${host || 'receiver'}`, COLOR_OK)
      self.render()
    }

    const finalize = (uploadId, dest, host) => {
      closeFd()
      self.setStatus(`Verifying on ${host || 'receiver'}…`, COLOR_BUSY)
      mb.request({ method: 'VN_FINISH', params: { upload_id: uploadId, dest } })
        .then((res) => {
          const { env, body } = hubFromSide(res)
          if (!env.ok || !body.ok) {
            fail(`Verify: ${body.error || env.error || 'failed'}`)
            return
          }
          dropLocal(host)
        })
        .catch((e) => fail(`Verify: ${errText(e)}`))
    }

    const sendChunk = (uploadId, dest, host, have, index) => {
      if (index >= total) {
        finalize(uploadId, dest, host)
        return
      }
      if (have[index]) {
        sendChunk(uploadId, dest, host, have, index + 1)
        return
      }

      const pos = index * CHUNK_BYTES
      const len = Math.min(CHUNK_BYTES, note.size - pos)
      let data
      let checksum
      try {
        const got = readSync({ fd, buffer: buf, options: { offset: 0, length: len, position: pos } })
        if (got !== len) throw new Error(`short read ${got}/${len}`)
        checksum = fnvHex(fnvUpdate(FNV_INIT, view, len))
        data = b64encode(view, len)
      } catch (e) {
        fail(`Read ${index + 1}/${total}: ${errText(e)}`)
        return
      }

      self.setStatus(`${host || 'Sending'} ${index + 1}/${total}`, COLOR_BUSY)

      mb.request({
        method: 'VN_CHUNK',
        params: { upload_id: uploadId, index, data, checksum, dest },
      })
        .then((res) => {
          const { env, body } = hubFromSide(res)
          if (!env.ok || !body.ok) {
            fail(`Chunk ${index + 1}/${total}: ${body.error || env.error || 'failed'}`)
            return
          }
          sendChunk(uploadId, dest, host, have, index + 1)
        })
        .catch((e) => fail(`Chunk ${index + 1}: ${errText(e)}`))
    }

    this.setStatus(`Starting ${total} chunks…`, COLOR_BUSY)
    mb.request({
      method: 'VN_BEGIN',
      params: {
        name: note.name,
        size: note.size,
        chunk_size: CHUNK_BYTES,
        total_chunks: total,
        sha,
      },
    })
      .then((res) => {
        const { env, body } = hubFromSide(res)
        if (!env.ok || !body.ok) {
          fail(`Begin: ${body.error || env.error || 'failed'}`)
          return
        }
        const dest = env.dest === undefined || env.dest === null ? 0 : Number(env.dest)
        const host = env.host || ''
        if (body.stored) {
          dropLocal(host)
          return
        }
        const have = {}
        ;(body.received || []).forEach((n) => {
          have[Number(n)] = true
        })
        try {
          fd = openSync({ path: note.name, flag: O_RDONLY })
        } catch (e) {
          fail(`Open: ${errText(e)}`)
          return
        }
        sendChunk(body.upload_id, dest, host, have, 0)
      })
      .catch((e) => fail(`Begin: ${errText(e)}`))
  },

  onDestroy() {
    this.state.busy = false
  },
})
