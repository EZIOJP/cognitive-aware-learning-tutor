/**
 * Continuous App Service — screen-off focus ticks.
 * Sensors: Time, Stress, HeartRate, Step (no Accel here).
 */
import { Time, Stress, HeartRate, Step } from '@zos/sensor'
import * as notificationMgr from '@zos/notification'
import { log as Logger } from '@zos/utils'
import { applySensorTick, loadSession, saveSession, startBreak, loadSettings } from '../shared/session'
import { MODE, PHASE } from '../shared/constants'

const logger = Logger.getLogger('af-service')

function readSample() {
  let stress = null
  let hr = null
  let restingHr = null
  let steps = null
  try {
    const st = new Stress()
    const cur = st.getCurrent()
    stress = cur && cur.value != null ? cur.value : null
  } catch (e) {
    logger.log('stress err')
  }
  try {
    const h = new HeartRate()
    hr = h.getLast()
    restingHr = h.getResting && h.getResting()
  } catch (e) {
    logger.log('hr err')
  }
  try {
    steps = new Step().getCurrent()
  } catch (e) {
    logger.log('step err')
  }
  return { stress, hr, restingHr, steps }
}

function notify(title, content) {
  try {
    notificationMgr.notify({
      title,
      content,
      actions: [],
      vibrate: 6,
    })
  } catch (e) {
    logger.log('notify fail')
  }
}

function handleEvents(events, session) {
  const settings = loadSettings()
  if (events.indexOf('extend') >= 0) {
    notify('Zone', 'Extended +5m — stay with it')
  }
  if (events.indexOf('spike') >= 0) {
    const next = startBreak(settings, PHASE.SPIKE, session.sessionCount || 0)
    notify('Breathe', 'Spike detected — guided break')
    return next
  }
  if (events.indexOf('fatigue_end') >= 0) {
    const count = (session.sessionCount || 0) + (session.mode === MODE.FOCUS ? 1 : 0)
    const next = startBreak(settings, PHASE.FATIGUE, count)
    next.sessionCount = count
    saveSession(next)
    notify('Rest', 'Fatigue — smart break started')
    return next
  }
  if (events.indexOf('focus_complete') >= 0) {
    const count = (session.sessionCount || 0) + 1
    const phase = session.phase || PHASE.NORMAL
    const next = startBreak(settings, phase, count)
    next.sessionCount = count
    saveSession(next)
    notify('Break', 'Focus done — smart break')
    return next
  }
  if (events.indexOf('break_complete') >= 0) {
    session.mode = MODE.IDLE
    session.running = false
    session.label = 'Ready'
    saveSession(session)
    notify('Ready', 'Break over — start next focus')
  }
  return session
}

AppService({
  onInit() {
    logger.log('focus service onInit')
    const timeSensor = new Time()
    timeSensor.onPerMinute(() => {
      try {
        const sample = readSample()
        const { session, events } = applySensorTick(sample)
        if (events && events.length) {
          handleEvents(events, session)
        }
      } catch (e) {
        logger.log(`tick error ${e}`)
      }
    })
    // Immediate first tick
    try {
      const sample = readSample()
      const { session, events } = applySensorTick(sample)
      if (events && events.length) handleEvents(events, session)
    } catch (e) {
      logger.log(`init tick ${e}`)
    }
  },
  onDestroy() {
    logger.log('focus service destroy')
  },
})
