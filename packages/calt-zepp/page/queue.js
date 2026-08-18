/**
 * Local 7-day full-dump queue + chunk resume + dump identity.
 */
import { localStorage } from '@zos/storage'

export const PENDING_QUEUE_KEY = 'calt_pending_sync_queue'
export const PENDING_QUEUE_DAYS = 7
export const CHUNK_RESUME_KEY = 'calt_chunk_resume'

export function localDateKey() {
  const d = new Date()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function readQueue() {
  try {
    const queue = JSON.parse(localStorage.getItem(PENDING_QUEUE_KEY) || '{}') || {}
    if (!queue || typeof queue !== 'object' || Array.isArray(queue)) return {}
    return queue
  } catch (_) {
    return {}
  }
}

function writeQueue(queue) {
  try {
    localStorage.setItem(PENDING_QUEUE_KEY, JSON.stringify(queue))
  } catch (_) {}
}

function pruneQueue(queue) {
  const cutoff = Date.now() - PENDING_QUEUE_DAYS * 24 * 60 * 60 * 1000
  Object.keys(queue).forEach((key) => {
    const stamp = Date.parse(`${key}T00:00:00`)
    if (!Number.isFinite(stamp) || stamp < cutoff) delete queue[key]
  })
  return queue
}

function hasSleep(health) {
  return !!(health && health.sleep && health.sleep.total_min)
}

/** Simple stable checksum for replay identity (not crypto). */
export function payloadChecksum(obj) {
  const s = JSON.stringify(obj || {})
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return `h${(h >>> 0).toString(16)}`
}

export function makeDumpId(day, capturedAt) {
  return `dump_${day}_${String(capturedAt || Date.now()).replace(/[^0-9A-Za-z]/g, '').slice(0, 20)}`
}

/**
 * Queue today's snapshot. force=true overwrites (manual Dump).
 */
export function queueSnapshot(health, opts) {
  if (!health) return
  const force = !!(opts && opts.force)
  try {
    const day = (opts && opts.day) || localDateKey()
    const queue = pruneQueue(readQueue())
    const current = queue[day]
    const incomingFull = health.dump === 'processed_v1'
    const incomingSleep = hasSleep(health)
    const currentSleep = hasSleep(current)

    const stamped = Object.assign({}, health)
    if (!stamped.captured_at) stamped.captured_at = new Date().toISOString()
    if (!stamped.local_date) stamped.local_date = day
    if (stamped.tz_offset_min == null) {
      try {
        stamped.tz_offset_min = -new Date().getTimezoneOffset()
      } catch (_) {}
    }
    if (!stamped.dump_id) stamped.dump_id = makeDumpId(day, stamped.captured_at)
    stamped.checksum = payloadChecksum({
      sleep: stamped.sleep,
      activity: stamped.activity,
      heart: stamped.heart,
      stress: stamped.stress,
      spo2: stamped.spo2,
    })

    if (force || !current) {
      if (force || incomingSleep || incomingFull) {
        if (force && !incomingSleep && currentSleep) {
          stamped.sleep = current.sleep
        }
        queue[day] = stamped
      }
    } else if (incomingFull && current.dump !== 'processed_v1') {
      if (!incomingSleep && currentSleep) stamped.sleep = current.sleep
      queue[day] = stamped
    } else if (incomingSleep && !currentSleep) {
      queue[day] = stamped
    }
    writeQueue(queue)
  } catch (_) {}
}

export function queuedDays() {
  const queue = pruneQueue(readQueue())
  writeQueue(queue)
  return Object.keys(queue).sort()
}

export function queueDepth() {
  return queuedDays().length
}

export function oldestQueuedSnapshot() {
  try {
    const queue = pruneQueue(readQueue())
    const day = Object.keys(queue).sort()[0]
    return day ? { day, health: queue[day] } : null
  } catch (_) {
    return null
  }
}

export function snapshotForDay(day) {
  const queue = readQueue()
  return queue[day] || null
}

export function removeQueuedSnapshot(day) {
  try {
    const queue = readQueue()
    delete queue[day]
    writeQueue(queue)
  } catch (_) {}
}

export function loadChunkResume() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHUNK_RESUME_KEY) || 'null')
    if (!raw || !raw.day) return null
    return { day: String(raw.day), nextPart: Number(raw.nextPart) || 0 }
  } catch (_) {
    return null
  }
}

export function saveChunkResume(day, nextPart) {
  try {
    localStorage.setItem(CHUNK_RESUME_KEY, JSON.stringify({ day, nextPart }))
  } catch (_) {}
}

export function clearChunkResume() {
  try {
    localStorage.removeItem(CHUNK_RESUME_KEY)
  } catch (_) {}
}

/** Split a full snapshot into small ingest parts with stable chunk ids. */
export function splitHealthChunks(health) {
  const h = health || {}
  const dump = h.dump || 'processed_v1'
  const dumpId = h.dump_id || makeDumpId(h.local_date || localDateKey(), h.captured_at)
  const clock = {
    captured_at: h.captured_at,
    local_date: h.local_date,
    tz_offset_min: h.tz_offset_min,
  }
  const parts = [
    { label: 'Sleep', health: { dump, dump_id: dumpId, ...clock, sleep: h.sleep, capabilities: h.capabilities } },
    {
      label: 'Activity',
      health: {
        dump,
        dump_id: dumpId,
        ...clock,
        activity: h.activity,
        calorie: h.calorie,
        distance: h.distance,
        stand: h.stand,
        battery: h.battery,
        sitting: h.sitting,
        capabilities: h.capabilities,
      },
    },
    { label: 'Heart', health: { dump, dump_id: dumpId, ...clock, heart: h.heart } },
    {
      label: 'Extras',
      health: {
        dump,
        dump_id: dumpId,
        ...clock,
        stress: h.stress,
        spo2: h.spo2,
        pai: h.pai,
        fat_burn: h.fat_burn,
        temperature: h.temperature,
        weather: h.weather,
        meta_device: h.meta_device,
        capabilities: h.capabilities,
      },
    },
  ]
  return parts.map((p, i) => ({
    ...p,
    chunk_id: `${dumpId}_${i + 1}`,
    checksum: payloadChecksum(p.health),
  }))
}
