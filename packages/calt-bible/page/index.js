/**
 * Today — current chapter, Read, swipe to settings.
 */
import { createWidget, widget, align, text_style } from '@zos/ui'
import { push } from '@zos/router'
import { onGesture, offGesture, GESTURE_LEFT } from '@zos/interaction'
import { screen, typeSize } from './layout'
import { ensurePlanDay, chapterLabel, nextChapterLabel } from '../lib/store'
import { readChapter, assetsOk } from '../lib/bible'

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
    try {
      this._build()
    } catch (e) {
      createWidget(widget.TEXT, {
        x: 28,
        y: 140,
        w: 424,
        h: 220,
        color: 0xff6666,
        text_size: 32,
        align_h: align.CENTER_H,
        text: `Bible error\n${e && e.message ? e.message : e}`,
      })
    }
  },

  _build() {
    const plan = ensurePlanDay()
    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.17)
    const ok = assetsOk()
    const ch = ok ? readChapter(plan.current_book, plan.current_chapter) : { verses: [] }
    const total = (ch.verses || []).length
    const title = ok ? chapterLabel(plan) : 'Assets missing'
    const status = !ok
      ? 'Re-sideload with bible JSON'
      : plan.plan_complete
        ? 'Plan complete'
        : `Next: ${nextChapterLabel(plan)}`

    createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.07),
      w: contentW,
      h: Math.round(height * 0.09),
      color: 0xffffff,
      text_size: typeSize(width, 'hero'),
      align_h: align.CENTER_H,
      text: 'CALT Bible',
    })

    this.titleW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.17),
      w: contentW,
      h: Math.round(height * 0.13),
      color: 0x88c0bb,
      text_size: typeSize(width, 'title'),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: title,
    })

    this.progW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.32),
      w: contentW,
      h: Math.round(height * 0.08),
      color: 0xaaaaaa,
      text_size: typeSize(width, 'label'),
      align_h: align.CENTER_H,
      text: !ok
        ? 'Bible text not installed'
        : total
          ? `${total} verses · full chapter`
          : 'No verses',
    })

    this.statusW = createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.41),
      w: contentW,
      h: Math.round(height * 0.09),
      color: 0xf0c674,
      text_size: typeSize(width, 'meta'),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: status,
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: Math.round(height * 0.52),
      w: contentW,
      h: btnH,
      radius: Math.round(btnH * 0.22),
      text: 'Read',
      text_size: typeSize(width, 'button'),
      normal_color: 0x1a9b8e,
      press_color: 0x147a70,
      click_func: () =>
        push({
          url: 'page/read',
          params: `${plan.current_book}|${plan.current_chapter}|${Number(plan.verse_cursor) || 0}`,
        }),
    })

    createWidget(widget.BUTTON, {
      x: pad,
      y: Math.round(height * 0.52) + btnH + Math.round(pad * 0.45),
      w: contentW,
      h: Math.round(btnH * 0.72),
      radius: Math.round(btnH * 0.18),
      text: 'Browse',
      text_size: typeSize(width, 'buttonSm'),
      normal_color: 0x2a4a6a,
      press_color: 0x1e364d,
      click_func: () => push({ url: 'page/books', params: 'browse|0' }),
    })

    createWidget(widget.TEXT, {
      x: pad,
      y: Math.round(height * 0.88),
      w: contentW,
      h: Math.round(height * 0.08),
      color: 0x666666,
      text_size: typeSize(width, 'caption'),
      align_h: align.CENTER_H,
      text: 'Swipe for settings',
    })
  },
})
