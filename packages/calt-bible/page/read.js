/**
 * Read a full chapter — scrollable verse list.
 * Larger type + padding for round-watch readability.
 *
 * Verses are batched into a few TEXT widgets (not one widget per verse) so
 * long chapters like Psalm 119 (176) do not exhaust watch RAM.
 */
import { createWidget, widget, align, text_style } from '@zos/ui'
import { back, replace } from '@zos/router'
import { screen, typeSize } from './layout'
import { readChapter } from '../lib/bible'
import { loadPlan, setCurrentChapter, savePlan } from '../lib/store'
import { splitParamsFrom } from '../lib/params'

/** Verses per TEXT block — keeps widget count low on long chapters. */
const VERSES_PER_BLOCK = 6

function estimateBlockHeight(text, contentW, textSize, width, height) {
  const charsPerLine = Math.max(16, Math.floor(contentW / (textSize * 0.58)))
  const lines = Math.max(2, Math.ceil(String(text).length / charsPerLine))
  const lineH = Math.round(textSize * 1.55)
  return Math.min(Math.round(height * 2.0), lines * lineH + Math.round(height * 0.03))
}

Page({
  onInit(params) {
    this._routeParams = params
  },

  build() {
    try {
      this._build()
    } catch (e) {
      createWidget(widget.TEXT, {
        x: 28,
        y: 120,
        w: 424,
        h: 220,
        color: 0xff6666,
        text_size: 32,
        align_h: align.CENTER_H,
        text: `Read error\n${e && e.message ? e.message : e}`,
      })
    }
  },

  _build() {
    const parts = splitParamsFrom(this._routeParams, 'genesis|1|0', 3)
    const plan = loadPlan()
    const bookId = parts[0] || plan.current_book
    const chapter = Number(parts[1]) || plan.current_chapter || 1

    const data = readChapter(bookId, chapter)
    const S = screen()
    const { pad, contentW, width, height } = S
    const verses = data.verses || []
    const isCurrent =
      plan.current_book === bookId && Number(plan.current_chapter) === Number(chapter)

    const vc = createWidget(widget.VIEW_CONTAINER, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      scroll_enable: 1,
    })

    let y = Math.round(height * 0.05)

    if (data.missing || !verses.length) {
      vc.createWidget(widget.TEXT, {
        x: pad,
        y: Math.round(height * 0.2),
        w: contentW,
        h: Math.round(height * 0.35),
        color: 0xff8888,
        text_size: typeSize(width, 'label'),
        align_h: align.CENTER_H,
        text_style: text_style.WRAP,
        text: data.missing
          ? 'Chapter file missing.\nRe-sideload CALT Bible.'
          : 'No verses in this chapter.',
      })
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y: Math.round(height * 0.6),
        w: contentW,
        h: Math.round(height * 0.13),
        text: 'Back',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x2a2a2a,
        press_color: 0x1a1a1a,
        click_func: () => back(),
      })
      return
    }

    if (isCurrent) {
      plan.verse_cursor = 0
      savePlan(plan)
    }

    const ref = `${data.name} ${data.chapter}`
    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.08),
      color: 0x88c0bb,
      text_size: typeSize(width, 'title'),
      align_h: align.CENTER_H,
      text_style: text_style.WRAP,
      text: ref,
    })
    y += Math.round(height * 0.09)

    vc.createWidget(widget.TEXT, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.055),
      color: 0x888888,
      text_size: typeSize(width, 'caption'),
      align_h: align.CENTER_H,
      text: `${verses.length} verses · scroll`,
    })
    y += Math.round(height * 0.07)

    const textSize = typeSize(width, 'verse')
    const blockGap = Math.round(pad * 0.5)
    for (let i = 0; i < verses.length; i += VERSES_PER_BLOCK) {
      const slice = verses.slice(i, i + VERSES_PER_BLOCK)
      const blockText = slice
        .map((v) => `${v.n}. ${String(v.t || '').trim()}`)
        .join('\n\n')
      const blockH = estimateBlockHeight(blockText, contentW, textSize, width, height)
      vc.createWidget(widget.TEXT, {
        x: pad,
        y,
        w: contentW,
        h: blockH,
        color: 0xffffff,
        text_size: textSize,
        align_h: align.LEFT,
        text_style: text_style.WRAP,
        text: blockText,
      })
      y += blockH + blockGap
    }

    y += Math.round(pad * 0.35)

    if (!isCurrent) {
      vc.createWidget(widget.BUTTON, {
        x: pad,
        y,
        w: contentW,
        h: Math.round(height * 0.12),
        radius: Math.round(height * 0.03),
        text: 'Set as current',
        text_size: typeSize(width, 'buttonSm'),
        normal_color: 0x333333,
        press_color: 0x222222,
        click_func: () => {
          setCurrentChapter(bookId, chapter)
          replace({ url: 'page/index' })
        },
      })
      y += Math.round(height * 0.14)
    }

    vc.createWidget(widget.BUTTON, {
      x: pad,
      y,
      w: contentW,
      h: Math.round(height * 0.11),
      radius: Math.round(height * 0.03),
      text: 'Back',
      text_size: typeSize(width, 'buttonSm'),
      normal_color: 0x2a2a2a,
      press_color: 0x1a1a1a,
      click_func: () => back(),
    })

    vc.createWidget(widget.TEXT, {
      x: pad,
      y: y + Math.round(height * 0.12),
      w: contentW,
      h: Math.round(height * 0.1),
      color: 0x000000,
      text_size: 12,
      text: ' ',
    })
  },
})
