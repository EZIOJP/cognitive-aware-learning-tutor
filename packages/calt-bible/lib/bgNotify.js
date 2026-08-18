/**
 * Schedule hourly verse (alarm) or fall back to a persisted App Service.
 * Zepp OS 6 prefers @zos/alarm — no per-minute Time sensor.
 */
import { queryPermission, requestPermission } from '@zos/app'
import { start as startService, stop as stopService, getAllAppServices } from '@zos/app-service'
import { log as Logger } from '@zos/utils'
import { loadPlan, takeNotifyVerse, markNotifyHour, hourStamp } from './store'
import { sendVerseNotification } from './notifyVerse'
import { startHourlyVerseAlarm, stopHourlyVerseAlarm } from './hourAlarm'

const logger = Logger.getLogger('calt-bible-bg')
export const SERVICE_FILE = 'app-service/bible'
const PERMS = ['device:os.bg_service', 'device:os.notification']

function granted(status) {
  return status === 2
}

export function serviceRunning() {
  try {
    const list = getAllAppServices ? getAllAppServices() : []
    if (!list || !list.length) return false
    return list.indexOf(SERVICE_FILE) >= 0 || list.indexOf('bible') >= 0
  } catch (_) {
    return false
  }
}

function withBgPerms(cb) {
  try {
    const result = queryPermission({ permissions: PERMS })
    const bg = result && result[0]
    const note = result && result[1]
    if (granted(bg) && (note == null || granted(note))) {
      cb(true)
      return
    }
    requestPermission({
      permissions: PERMS,
      callback(res) {
        cb(!!(res && granted(res[0])))
      },
    })
  } catch (e) {
    logger.log(`perm ${e}`)
    cb(false)
  }
}

function startPersistedService(cb) {
  withBgPerms((ok) => {
    if (!ok) {
      logger.log('bg/notify permission denied')
      if (cb) cb(false)
      return
    }
    try {
      startService({
        file: SERVICE_FILE,
        persist: true,
        complete(r) {
          logger.log(`start ${JSON.stringify(r)}`)
          if (cb) cb(true)
        },
      })
    } catch (e) {
      logger.log(`startService ${e}`)
      if (cb) cb(false)
    }
  })
}

export function stopBibleService() {
  stopHourlyVerseAlarm()
  try {
    stopService({
      file: SERVICE_FILE,
      complete() {},
    })
  } catch (_) {}
}

export function startBibleService(cb) {
  startHourlyVerseAlarm((ok) => {
    if (ok) {
      if (cb) cb(true)
      return
    }
    logger.log('alarm failed — persist service fallback')
    startPersistedService(cb)
  })
}

export function sendTestVerseNow() {
  const plan = loadPlan()
  if (plan.notify_mode === 'off') return { ok: false, reason: 'Notify is off' }
  const verse = takeNotifyVerse()
  if (!verse) return { ok: false, reason: 'No verse (check Bible files)' }
  const ok = sendVerseNotification(verse, 6)
  if (ok) {
    try {
      markNotifyHour(hourStamp())
    } catch (_) {}
  }
  startBibleService()
  return ok ? { ok: true, ref: verse.ref } : { ok: false, reason: 'Notify API failed' }
}

export function ensureNotifyRunning() {
  const plan = loadPlan()
  if (plan.notify_mode === 'off') {
    stopBibleService()
    return
  }
  startBibleService()
}
