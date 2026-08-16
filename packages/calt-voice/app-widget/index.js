/**
 * Shortcut card — opens black-screen recorder (auto-starts).
 */
import { createWidget, widget, align } from '@zos/ui'
import { push } from '@zos/router'
import { getDeviceInfo } from '@zos/device'

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

    createWidget(widget.TEXT, {
      x: 16,
      y: 40,
      w: width - 32,
      h: 40,
      color: 0xff4444,
      text_size: 28,
      align_h: align.CENTER_H,
      text: '● Voice',
    })

    createWidget(widget.TEXT, {
      x: 16,
      y: 90,
      w: width - 32,
      h: 40,
      color: 0xaaaaaa,
      text_size: 20,
      align_h: align.CENTER_H,
      text: 'Tap → record',
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
  },
})
