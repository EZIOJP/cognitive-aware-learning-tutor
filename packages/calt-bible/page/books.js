/**
 * Book list — paginated (avoids widget OOM / black screen).
 */
import { createWidget, widget, align } from '@zos/ui'
import { back, push, replace } from '@zos/router'
import { screen, typeSize } from './layout'
import { listBooks, assetsOk } from '../lib/bible'
import { splitParamsFrom } from '../lib/params'

const PAGE_SIZE = 12

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
        text: `Books error\n${e && e.message ? e.message : e}`,
      })
    }
  },

  _build() {
    const parts = splitParamsFrom(this._routeParams, 'browse|0', 2)
    const mode = parts[0] || 'browse'
    const page = Math.max(0, Number(parts[1]) || 0)
    const S = screen()
    const { pad, contentW, width, height } = S
    const btnH = Math.round(height * 0.125)
    const gap = Math.round(pad * 0.45)
    const books = listBooks()

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
      text: mode === 'set' ? 'Set book' : 'Books',
    })
    y += Math.round(height * 0.1)

    if (!assetsOk() || !books.length) {
      vc.createWidget(widget.TEXT, {
        x: pad,
        y,
        w: contentW,
        h: Math.round(height * 0.35),
        color: 0xff8888,
        text_size: typeSize(width, 'label'),
        align_h: align.CENTER_H,
        text: 'Bible files not found.\nRe-sideload CALT Bible\n(assets missing).',
      })
      y += Math.round(height * 0.38)
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
      return
    }

    const totalPages = Math.max(1, Math.ceil(books.length / PAGE_SIZE))
    const safePage = Math.min(page, totalPages - 1)
    const start = safePage * PAGE_SIZE
    const slice = books.slice(start, start + PAGE_SIZE)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y: y - Math.round(height * 0.02),
      w: contentW,
      h: Math.round(height * 0.05),
      color: 0x888888,
      text_size: typeSize(width, 'caption'),
      align_h: align.CENTER_H,
      text: `${safePage + 1}/${totalPages}  ·  ${books.length} books`,
    })
    y += Math.round(height * 0.05)

    for (let i = 0; i < slice.length; i++) {
      const b = slice[i]
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: `${b.name}  (${b.n})`,
        text_size: typeSize(width, 'label'),
        normal_color: String(b.testament || '').toUpperCase() === 'NT' ? 0x2a4a6a : 0x333333,
        press_color: 0x1a1a1a,
        click_func: () =>
          push({
            url: 'page/chapters',
            params: `${b.id}|${mode}|0`,
          }),
      })
      y += btnH + gap
    }

    if (safePage > 0) {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: btnH,
        radius: Math.round(btnH * 0.22),
        text: 'Prev books',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x2a4a6a,
        press_color: 0x1e364d,
        click_func: () =>
          replace({ url: 'page/books', params: `${mode}|${safePage - 1}` }),
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
        text: 'More books',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x2a4a6a,
        press_color: 0x1e364d,
        click_func: () =>
          replace({ url: 'page/books', params: `${mode}|${safePage + 1}` }),
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
    y += btnH + gap
    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.08),
      color: 0x000000,
      text_size: 12,
      text: ' ',
    })
  },
})
