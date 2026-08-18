/**
 * Zepp OS 6: hourly verse via @zos/alarm, not Time.onPerMinute.
 * Alarm wakes the App Service once an hour, then the service exits.
 */
import { queryPermission, requestPermission } from '@zos/app'
import { set as setAlarm, cancel as cancelAlarm, getAllAlarms } from '@zos/alarm'
import { Time } from '@zos/sensor'
import { localStorage } from '@zos/storage'
import { log as Logger } from '@zos/utils'

const logger = Logger.getLogger('calt-bible-alarm')
const KEY = 'calt_bible_alarm_id'
const SERVICE = 'app-service/bible'
const PERM = ['device:os.alarm']

function granted(status) {
  return status === 2
}

function withAlarmPerm(cb) {
  try {
    const result = queryPermission({ permissions: PERM })
    if (result && granted(result[0])) {
      cb(true)
      return
    }
    requestPermission({
      permissions: PERM,
      callback(res) {
        cb(!!(res && granted(res[0])))
      },
    })
  } catch (e) {
    logger.log(`perm ${e}`)
    cb(false)
  }
}

function nextHourUtcSec() {
  let delay = 3600
  try {
    const t = new Time()
    const mins = t.getMinutes()
    const secs = typeof t.getSeconds === 'function' ? t.getSeconds() : 0
    delay = Math.max(60, (60 - mins) * 60 - secs)
  } catch (_) {}
  return Math.floor(Date.now() / 1000) + delay
}

function clearStored() {
  try {
    const id = Number(localStorage.getItem(KEY) || 0)
    if (id) cancelAlarm(id)
  } catch (_) {}
  try {
    const all = getAllAlarms()
    if (all && all.length) {
      for (let i = 0; i < all.length; i++) {
        try {
          cancelAlarm(all[i])
        } catch (__) {}
      }
    }
  } catch (_) {}
  try {
    localStorage.removeItem(KEY)
  } catch (_) {}
}

export function stopHourlyVerseAlarm() {
  clearStored()
}

export function startHourlyVerseAlarm(cb) {
  withAlarmPerm((ok) => {
    if (!ok) {
      logger.log('alarm permission denied')
      if (cb) cb(false)
      return
    }
    clearStored()
    try {
      const id = setAlarm({
        url: SERVICE,
        time: nextHourUtcSec(),
        store: true,
      })
      if (id) {
        try {
          localStorage.setItem(KEY, String(id))
        } catch (_) {}
        logger.log(`alarm ${id}`)
        if (cb) cb(true)
        return
      }
    } catch (e) {
      logger.log(`setAlarm ${e}`)
    }
    if (cb) cb(false)
  })
}
