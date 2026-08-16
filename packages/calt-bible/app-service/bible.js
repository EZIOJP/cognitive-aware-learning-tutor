/**
 * Midnight chapter advance + hourly verse from current chapter (08:00–21:00).
 */
import { Time } from '@zos/sensor'
import * as notificationMgr from '@zos/notification'
import { log as Logger } from '@zos/utils'
import {
  ensurePlanDay,
  takeNotifyVerse,
  loadPlan,
  markNotifyHour,
  todayKey,
} from '../lib/store'

const logger = Logger.getLogger('calt-bible')

function hourKey(timeSensor) {
  const day = todayKey()
  try {
    const h = timeSensor.getHours()
    return `${day}T${h < 10 ? '0' : ''}${h}`
  } catch (_) {
    return `${day}T00`
  }
}

function maybeNotify(timeSensor) {
  const plan = loadPlan()
  if (plan.notify_mode !== 'hourly') return
  let hour = 0
  try {
    hour = timeSensor.getHours()
  } catch (_) {
    return
  }
  if (hour < 8 || hour > 21) return
  const key = hourKey(timeSensor)
  if (plan.notify_hour_key === key) return
  const verse = takeNotifyVerse()
  if (!verse) return
  try {
    notificationMgr.notify({
      title: String(verse.ref || 'CALT Bible').slice(0, 48),
      content: String(verse.text || '').slice(0, 120),
      actions: [],
      vibrate: 1,
    })
    markNotifyHour(key)
  } catch (e) {
    logger.log(`notify ${e}`)
  }
}

AppService({
  onInit() {
    logger.log('bible service onInit')
    ensurePlanDay()
    const timeSensor = new Time()
    maybeNotify(timeSensor)
    timeSensor.onPerMinute(() => {
      try {
        const m = timeSensor.getMinutes()
        if (m === 0) {
          ensurePlanDay()
          maybeNotify(timeSensor)
        }
      } catch (err) {
        logger.log(`tick ${err}`)
      }
    })
  },
  onDestroy() {
    logger.log('bible service destroy')
  },
})
