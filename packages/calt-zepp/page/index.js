/**
 * Manual health dumper — Dump captures, Send flushes queue. No autosync.
 */
import { createWidget, widget, align, text_style, prop } from '@zos/ui'
import { push } from '@zos/router'
import { onGesture, offGesture, GESTURE_LEFT } from '@zos/interaction'
import { localStorage } from '@zos/storage'
import { log } from '@zos/utils'
import { buildHealthSnapshot, snapshotSummary, sleepDisplayMinutes } from './sensors'
import { screen } from './layout'
import {
  queueSnapshot,
  snapshotForDay,
  removeQueuedSnapshot,
  localDateKey,
  splitHealthChunks,
  loadChunkResume,
  saveChunkResume,
  clearChunkResume,
  queuedDays,
  queueDepth,
} from './queue'

const logger = log.getLogger('calt-dump')

function saveWatchLog(result, health) {
  let logs = []
  try {
    logs = JSON.parse(localStorage.getItem('calt_sync_log') || '[]')
  } catch (_) {
    logs = []
  }
  if (!Array.isArray(logs)) logs = []
  logs.unshift({
    at: result.plansFetchedAt || new Date().toISOString(),
    ok: !!(result.healthOk && !(result.errors || []).length),
    summary: result.summary || '',
    errors: result.errors || [],
    diag: result.diag || '',
    host: result.host || '',
    steps: (health.activity && health.activity.steps) || result.steps,
    sleep_min: sleepDisplayMinutes(health) || result.sleepMin,
    wrote_life: !!result.wroteLife,
    base: result.base || '',
    replay: !!(result.replayed || result.duplicate),
  })
  logs = logs.slice(0, 20)
  try {
    localStorage.setItem('calt_sync_log', JSON.stringify(logs))
  } catch (_) {}
}

function cacheSyncResult(result) {
  try {
    localStorage.setItem('calt_last_summary', result.summary || result.diag || '')
    const snap = {
      steps: result.steps,
      sleep_min: result.sleepMin,
      hr: result.hr,
      stand: result.standHours,
      battery: result.batteryPct,
    }
    localStorage.setItem('calt_last_payload', JSON.stringify(snap))
  } catch (_) {}
}

Page({
  onInit() {
    onGesture((event) => {
      if (event === GESTURE_LEFT) {
        push({ url: 'page/settings' })
        return true
      }
      return false
    })
  },

  onDestroy() {
    try {
      offGesture()
    } catch (_) {}
  },

  build() {
    const { messageBuilder } = getApp().globalData || getApp()._options.globalData || {}
    if (!messageBuilder) {
      createWidget(widget.TEXT, {
        x: 20,
        y: 80,
        w: 440,
        h: 80,
        color: 0xff6666,
        text_size: 22,
        align_h: align.CENTER_H,
        text: 'BLE not ready — reopen app',
      })
      return
    }

    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.14)
    const gap = Math.round(pad * 0.35)

    // Preview only — do NOT auto-queue or auto-send
    const health0 = buildHealthSnapshot('full')
    this._preview = health0

    createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.06),
      w: contentW,
      h: Math.round(height * 0.07),
      color: 0xffffff,
      text_size: Math.round(width * 0.055),
      align_h: align.CENTER_H,
      text: 'CALT Dump',
    })

    this.snapW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.14),
      w: contentW,
      h: Math.round(height * 0.16),
      color: 0x88c0bb,
      text_size: Math.round(width * 0.036),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: snapshotSummary(health0),
    })

    this.queueW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.31),
      w: contentW,
      h: Math.round(height * 0.07),
      color: 0xf0c674,
      text_size: Math.round(width * 0.032),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: `Queue ${queueDepth()}/7 days`,
    })

    this.statusW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.39),
      w: contentW,
      h: Math.round(height * 0.08),
      color: 0xaaaaaa,
      text_size: Math.round(width * 0.032),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: 'Manual only · Dump then Send',
    })

    let y = Math.round(height * 0.5)
    createWidget(widget.BUTTON, {
      x: pad,
      y,
      w: contentW,
      h: btnH,
      radius: Math.round(btnH * 0.22),
      text: 'Dump today',
      text_size: Math.round(width * 0.045),
      normal_color: 0x2a4a6a,
      press_color: 0x1e364d,
      click_func: () => this.doDump(),
    })
    y += btnH + gap

    createWidget(widget.BUTTON, {
      x: pad,
      y,
      w: contentW,
      h: btnH,
      radius: Math.round(btnH * 0.22),
      text: 'Send queue',
      text_size: Math.round(width * 0.045),
      normal_color: 0x1a9b8e,
      press_color: 0x147a70,
      click_func: () => this.doSend(messageBuilder),
    })
    y += btnH + gap

    createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.06),
      color: 0x666666,
      text_size: Math.round(width * 0.028),
      align_h: align.CENTER_H,
      text: 'Swipe · settings / log',
    })

    try {
      const last = localStorage.getItem('calt_last_summary')
      if (last) this.statusW.setProperty(prop.TEXT, last)
    } catch (_) {}
  },

  setStatus(text) {
    if (this.statusW) this.statusW.setProperty(prop.TEXT, text)
  },

  refreshQueueLabel() {
    if (this.queueW) {
      const days = queuedDays()
      this.queueW.setProperty(
        prop.TEXT,
        days.length ? `Queue ${days.length}/7 · ${days.join(',')}` : 'Queue empty',
      )
    }
  },

  doDump() {
    this.setStatus('Capturing…')
    const health = buildHealthSnapshot('full')
    this._preview = health
    queueSnapshot(health, { force: true })
    if (this.snapW) this.snapW.setProperty(prop.TEXT, snapshotSummary(health))
    this.refreshQueueLabel()
    this.setStatus('Queued today · press Send')
  },

  doSend(messageBuilder) {
    if (this._syncing) return
    this._syncing = true
    this.setStatus('Sending…')

    const today = localDateKey()
    // Ensure today exists if user forgot Dump
    if (queuedDays().indexOf(today) < 0) {
      const health = buildHealthSnapshot('full')
      this._preview = health
      queueSnapshot(health, { force: true })
      if (this.snapW) this.snapW.setProperty(prop.TEXT, snapshotSummary(health))
    }

    const days = queuedDays()
    const resume = loadChunkResume()
    if (resume && resume.day && days.indexOf(resume.day) < 0) {
      days.unshift(resume.day)
    }
    if (!days.length) {
      this._syncing = false
      this.setStatus('Nothing to send')
      return
    }

    const self = this
    let resumeApplied = false
    const preview = this._preview || buildHealthSnapshot('full')

    const runDay = (dayIndex) => {
      if (dayIndex >= days.length) {
        clearChunkResume()
        self._syncing = false
        self.refreshQueueLabel()
        self.setStatus('Done')
        return
      }
      const day = days[dayIndex]
      const dayHealth = snapshotForDay(day) || (day === today ? preview : null)
      if (!dayHealth) {
        removeQueuedSnapshot(day)
        runDay(dayIndex + 1)
        return
      }
      const chunks = splitHealthChunks(dayHealth)
      let startPart = 0
      if (!resumeApplied && resume && resume.day === day) {
        startPart = resume.nextPart || 0
        resumeApplied = true
      }

      const runPart = (partIndex) => {
        if (partIndex >= chunks.length) {
          removeQueuedSnapshot(day)
          saveChunkResume(days[dayIndex + 1] || '', 0)
          self.refreshQueueLabel()
          runDay(dayIndex + 1)
          return
        }
        const chunk = chunks[partIndex]
        self.setStatus(`${day} ${chunk.label} ${partIndex + 1}/${chunks.length}`)
        messageBuilder
          .request({
            method: 'SYNC',
            params: {
              health: chunk.health,
              localDate: day,
              queuedSleepSnapshot: day !== today,
              skipFollowup: true,
              chunk: {
                part: partIndex + 1,
                total: chunks.length,
                label: chunk.label,
                dump: 'processed_v1',
                day,
                chunk_id: chunk.chunk_id,
                dump_id: dayHealth.dump_id,
                checksum: chunk.checksum,
              },
            },
          })
          .then((res) => {
            const result = res || {}
            cacheSyncResult(result)
            saveWatchLog(result, dayHealth)
            if (!result.healthOk) {
              saveChunkResume(day, partIndex)
              self._syncing = false
              self.setStatus(result.summary || 'Retry queued')
              return
            }
            saveChunkResume(day, partIndex + 1)
            runPart(partIndex + 1)
          })
          .catch((e) => {
            saveChunkResume(day, partIndex)
            self._syncing = false
            self.setStatus(`Retry · ${e}`)
            logger.log(`send ${e}`)
          })
      }

      runPart(startPart)
    }

    runDay(0)
  },
})
