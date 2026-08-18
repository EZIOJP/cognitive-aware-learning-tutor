/**
 * Hourly verse from current chapter (08:00–21:00).
 * Zepp OS 6: woken by a one-shot @zos/alarm, then reschedules and exits.
 */
import { Time } from '@zos/sensor'
import { log as Logger } from '@zos/utils'
import * as appServiceMgr from '@zos/app-service'
import {
  ensurePlanDay,
  takeNotifyVerse,
  loadPlan,
  markNotifyHour,
  hourStamp,
} from '../lib/store'
import { sendVerseNotification } from '../lib/notifyVerse'
import { startHourlyVerseAlarm } from '../lib/hourAlarm'

const logger = Logger.getLogger('calt-bible')

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
  const key = hourStamp(hour)
  if (plan.notify_hour_key === key) return
  const verse = takeNotifyVerse()
  if (!verse) {
    logger.log('no verse')
    return
  }
  if (sendVerseNotification(verse, 6)) {
    markNotifyHour(key)
    logger.log(`notified ${verse.ref}`)
  }
}

AppService({
  onEvent(e) {
    logger.log(`onEvent ${e}`)
    const s = String(e || '')
    if (s.indexOf('action=exit') >= 0 || s.indexOf('action=stop') >= 0) {
      try {
        appServiceMgr.exit()
      } catch (_) {}
    }
  },
  onInit() {
    logger.log('bible alarm wake')
    ensurePlanDay()
    try {
      maybeNotify(new Time())
    } catch (err) {
      logger.log(`notify ${err}`)
    }
    const finish = () => {
      try {
        appServiceMgr.exit()
      } catch (_) {}
    }
    const plan = loadPlan()
    if (plan.notify_mode !== 'hourly') {
      finish()
      return
    }
    try {
      startHourlyVerseAlarm(() => finish())
    } catch (_) {
      finish()
    }
  },
  onDestroy() {
    logger.log('bible service destroy')
  },
})
