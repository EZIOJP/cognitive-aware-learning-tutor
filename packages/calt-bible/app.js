import { ensureNotifyRunning } from './lib/bgNotify'

App({
  globalData: {},
  onCreate() {
    try {
      ensureNotifyRunning()
    } catch (_) {}
  },
  onDestroy() {},
})
