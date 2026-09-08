/**
 * Shortcut card — opens clock / voice recorder.
 */
import { createWidget, widget, align, prop } from '@zos/ui'
import { push } from '@zos/router'
import { getDeviceInfo } from '@zos/device'

function pad2(n) {
  return n < 10 ? `0${n}` : `${n}`
}

function fmtClock(d) {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

AppWidget({
  build() {
    let width = 480
    let height = 200
    try {
      const info = getDeviceInfo()
      width = info.width || width
    } catch (_) {}

    createWidget(widget.FILL_RECT, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      color: 0x111111,
      radius: 24,
    })

    const clockW = createWidget(widget.TEXT, {
      x: 16,
      y: 36,
      w: width - 32,
      h: 56,
      color: 0xffffff,
      text_size: 44,
      align_h: align.CENTER_H,
      text: fmtClock(new Date()),
    })

    createWidget(widget.TEXT, {
      x: 16,
      y: 100,
      w: width - 32,
      h: 36,
      color: 0x888888,
      text_size: 18,
      align_h: align.CENTER_H,
      text: 'Tap for voice',
    })

    createWidget(widget.BUTTON, {
      x: 0,
      y: 0,
      w: width,
      h: height,
      text: ' ',
      normal_color: 0x000000,
      press_color: 0x222222,
      click_func: () => {
        push({ url: 'page/index' })
      },
    })

    try {
      setInterval(() => {
        try {
          clockW.setProperty(prop.TEXT, fmtClock(new Date()))
        } catch (_) {}
      }, 1000)
    } catch (_) {}
  },
})
