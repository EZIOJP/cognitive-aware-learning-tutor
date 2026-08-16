/**
 * Chapter list for one book — paginated grid.
 */
import { createWidget, widget, align } from '@zos/ui'
import { back, push, replace } from '@zos/router'
import { screen, typeSize } from './layout'
import { chapterCount, bookName } from '../lib/bible'
import { setCurrentChapter } from '../lib/store'
import { splitParamsFrom } from '../lib/params'

const PAGE_SIZE = 30

Page({
  onInit(params) {
    this._routeParams = params
  },

  build() {
    try {
      this._build()
    } catch (e) {
      createWidget(widget.TEXT, {
        x: 24,
        y: 120,
        w: 432,
        h: 200,
        color: 0xff6666,
        text_size: 28,
        align_h: align.CENTER_H,
        text: `Chapters error\n${e && e.message ? e.message : e}`,
      })
    }
  },

  _build() {
    const parts = splitParamsFrom(this._routeParams, 'genesis|browse|0', 3)
    const bookId = parts[0] || 'genesis'
    const mode = parts[1] || 'browse'
    const page = Math.max(0, Number(parts[2]) || 0)
    const n = chapterCount(bookId)
    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.125)
    const gap = Math.round(pad * 0.4)
    const name = bookName(bookId)

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
      text: name,
    })
    y += Math.round(height * 0.1)

    if (!n) {
      vc.createWidget(widget.TEXT, {
        x: pad,
        y,
        w: contentW,
        h: Math.round(height * 0.3),
        color: 0xff8888,
        text_size: typeSize(width, 'label'),
        align_h: align.CENTER_H,
        text: `Missing ${bookId}\nRe-sideload app.`,
      })
      y += Math.round(height * 0.32)
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        text: 'Back',
        normal_color: 0x1a9b8e,
        press_color: 0x147a70,
        click_func: () => back(),
      })
      return
    }

    const totalPages = Math.max(1, Math.ceil(n / PAGE_SIZE))
    const safePage = Math.min(page, totalPages - 1)
    const start = safePage * PAGE_SIZE + 1
    const end = Math.min(n, start + PAGE_SIZE - 1)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y: y - Math.round(height * 0.02),
      w: contentW,
      h: Math.round(height * 0.05),
      color: 0x888888,
      text_size: typeSize(width, 'caption'),
      align_h: align.CENTER_H,
      text: `Ch ${start}–${end}  ·  ${safePage + 1}/${totalPages}`,
    })
    y += Math.round(height * 0.05)

    const colW = Math.round((contentW - gap) / 2)
    let col = 0
    for (let c = start; c <= end; c++) {
      const x = pad + col * (colW + gap)
      vc.createWidget(widget.BUTTON, {
        x,
        y,
        w: colW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: String(c),
        text_size: typeSize(width, 'button'),
        normal_color: 0x333333,
        press_color: 0x1a1a1a,
        click_func: () => {
          if (mode === 'set') {
            setCurrentChapter(bookId, c)
            replace({ url: 'page/index' })
            return
          }
          push({ url: 'page/read', params: `${bookId}|${c}|0` })
        },
      })
      col += 1
      if (col >= 2) {
        col = 0
        y += btnH + gap
      }
    }
    if (col === 1) y += btnH + gap

    if (safePage > 0) {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: 'Prev chapters',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x2a4a6a,
        press_color: 0x1e364d,
        click_func: () =>
          replace({
            url: 'page/chapters',
            params: `${bookId}|${mode}|${safePage - 1}`,
          }),
      })
      y += btnH + gap
    }
    if (safePage < totalPages - 1) {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: 'More chapters',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x2a4a6a,
        press_color: 0x1e364d,
        click_func: () =>
          replace({
            url: 'page/chapters',
            params: `${bookId}|${mode}|${safePage + 1}`,
          }),
      })
      y += btnH + gap
    }

    vc.createWidget(widget.BUTTON, {
      x: pad,
      y,
      w: contentW,
      h: btnH,
      radius: Math.round(btnH * 0.22),
      text: 'Back',
      text_size: typeSize(width, 'buttonSm'),
      normal_color: 0x1a9b8e,
      press_color: 0x147a70,
      click_func: () => back(),
    })
  },
})
