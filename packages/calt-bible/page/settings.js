/**
 * Settings — current chapter + notify mode.
 */
import { createWidget, widget, align, text_style, prop } from '@zos/ui'
import { back, push } from '@zos/router'
import { onGesture, offGesture, GESTURE_RIGHT } from '@zos/interaction'
import { screen, typeSize } from './layout'
import {
  ensurePlanDay,
  chapterLabel,
  nextChapterLabel,
  setNotifyMode,
  loadPlan,
} from '../lib/store'
import { ensureNotifyRunning, sendTestVerseNow, stopBibleService } from '../lib/bgNotify'

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
    const plan = ensurePlanDay()
    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.135)
    const gap = Math.round(pad * 0.5)

    const vc = createWidget(widget.VIEW_CONTAINER, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      scroll_enable: 1,
    })

    let y = Math.round(height * 0.05)
    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.07),
      color: 0xffffff,
      text_size: typeSize(width, 'title'),
      align_h: align.CENTER_H,
      text: 'Settings',
    })
    y += Math.round(height * 0.1)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.13),
      color: 0x88c0bb,
      text_size: typeSize(width, 'label'),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: `Current\n${chapterLabel(plan)}`,
    })
    y += Math.round(height * 0.15)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.09),
      color: 0xf0c674,
      text_size: typeSize(width, 'meta'),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: `Tomorrow: ${nextChapterLabel(plan)}`,
    })
    y += Math.round(height * 0.11)

    this.notifyW = vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.09),
      color: 0xaaaaaa,
      text_size: typeSize(width, 'meta'),
      align_h: align.CENTER_H,
      text: plan.notify_mode === 'off' ? 'Notify off' : 'Notify hourly 8-21',
    })
    y += Math.round(height * 0.11)

    const addBtn = (label, color, press, onClick) => {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: label,
        text_size: typeSize(width, 'buttonSm'),
        normal_color: color,
        press_color: press,
        click_func: onClick,
      })
      y += btnH + gap
    }

    addBtn('Set current chapter', 0x2a4a6a, 0x1e364d, () =>
      push({ url: 'page/books', params: 'set|0' }),
    )
    addBtn(
      plan.notify_mode === 'off' ? 'Turn notify on' : 'Turn notify off',
      0x333333,
      0x222222,
      () => {
        const current = loadPlan()
        const next = current.notify_mode === 'off' ? 'hourly' : 'off'
        const updated = setNotifyMode(next)
        this.notifyW.setProperty(
          prop.TEXT,
          updated.notify_mode === 'off' ? 'Notify off' : 'Notify hourly 8-21',
        )
        if (updated.notify_mode === 'off') stopBibleService()
        else ensureNotifyRunning()
      },
    )
    addBtn('Send verse now', 0x2a4a6a, 0x1e364d, () => {
      const r = sendTestVerseNow()
      try {
        const ui = require('@zos/interaction')
        if (ui && ui.showToast) {
          ui.showToast({
            text: r.ok ? `Sent ${r.ref}` : r.reason || 'Notify failed',
          })
        }
      } catch (_) {}
    })
    addBtn('Browse Bible', 0x333333, 0x222222, () =>
      push({ url: 'page/books', params: 'browse|0' }),
    )
    addBtn('Back', 0x1a9b8e, 0x147a70, () => back())
  },
})
