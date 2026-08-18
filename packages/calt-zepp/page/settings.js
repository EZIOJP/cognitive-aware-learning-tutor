/**
 * Settings — host + queue + log. Health dump only.
 */
import { createWidget, widget, align, text_style, prop } from '@zos/ui'
import { push, back } from '@zos/router'
import { onGesture, offGesture, GESTURE_RIGHT } from '@zos/interaction'
import { localStorage } from '@zos/storage'
import { screen } from './layout'
import { queuedDays, loadChunkResume } from './queue'
import { formatHoursMins } from '../shared/timeFmt'

function payloadSummary() {
  try {
    const raw = JSON.parse(localStorage.getItem('calt_last_payload') || 'null')
    if (!raw) return 'No payload yet'
    const parts = []
    if (raw.sleep_min != null) parts.push(`${formatHoursMins(raw.sleep_min)} sleep`)
    if (raw.steps != null) parts.push(`${raw.steps} st`)
    if (raw.hr != null) parts.push(`HR ${raw.hr}`)
    if (raw.stand != null) parts.push(`stand ${raw.stand}h`)
    if (raw.battery != null) parts.push(`bat ${raw.battery}%`)
    return parts.length ? parts.join(' · ') : 'No payload yet'
  } catch (_) {
    return 'No payload yet'
  }
}

Page({
  onInit() {
    onGesture((event) => {
      if (event === GESTURE_RIGHT) {
        back()
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
    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.12)
    const gap = Math.round(pad * 0.4)

    const vc = createWidget(widget.VIEW_CONTAINER, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      scroll_enable: 1,
    })

    let y = Math.round(height * 0.06)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.07),
      color: 0xffffff,
      text_size: Math.round(width * 0.05),
      align_h: align.CENTER_H,
      text: 'Settings',
    })
    y += Math.round(height * 0.08)

    this.hostW = vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.1),
      color: 0x88c0bb,
      text_size: Math.round(width * 0.032),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: 'Host —',
    })
    y += Math.round(height * 0.12)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.06),
      color: 0xaaaaaa,
      text_size: Math.round(width * 0.03),
      align_h: align.CENTER_H,
      text: 'Manual health dump · no plans',
    })
    y += Math.round(height * 0.07)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.12),
      color: 0xffffff,
      text_size: Math.round(width * 0.032),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: `Last send\n${payloadSummary()}`,
    })
    y += Math.round(height * 0.14)

    const days = queuedDays()
    const resume = loadChunkResume()
    const gapLine = days.length
      ? `Queued ${days.join(', ')}${resume && resume.day ? `\nResume ${resume.day} #${resume.nextPart}` : ''}`
      : 'Queue empty — Dump today first'
    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.14),
      color: 0xf0c674,
      text_size: Math.round(width * 0.03),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: gapLine,
    })
    y += Math.round(height * 0.15)

    const addBtn = (label, color, press, onClick) => {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: label,
        text_size: Math.round(width * 0.038),
        normal_color: color,
        press_color: press,
        click_func: onClick,
      })
      y += btnH + gap
    }

    addBtn('Sync log', 0x333333, 0x222222, () => push({ url: 'page/log' }))
    addBtn('Back', 0x1a9b8e, 0x147a70, () => back())

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.1),
      color: 0x000000,
      text_size: 12,
      text: ' ',
    })

    if (messageBuilder) {
      messageBuilder
        .request({ method: 'GET_SETTINGS' })
        .then((s) => {
          const host = (s && (s.host || s.last_good_host || s.base_url)) || '—'
          this.hostW.setProperty(prop.TEXT, `Host ${host}`)
        })
        .catch(() => {})
    }
  },
})
