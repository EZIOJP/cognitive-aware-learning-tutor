/**
 * Side Service — health dump POST only (manual CALT Sync 4.0).
 */
import { MessageBuilder } from '../shared/message-side'

const messageBuilder = new MessageBuilder()
const MAX_LOG = 20
const APP_VER = '4.1.0'

function settingsGet(key, fallback = '') {
  try {
    if (typeof settings !== 'undefined' && settings.settingsStorage) {
      const v = settings.settingsStorage.getItem(key)
      if (v !== undefined && v !== null && v !== '') return v
    }
  } catch (_) {}
  return fallback
}

function settingsSet(key, value) {
  try {
    if (typeof settings !== 'undefined' && settings.settingsStorage) {
      settings.settingsStorage.setItem(key, String(value))
    }
  } catch (_) {}
}

function normalizeBaseUrl(raw) {
  let u = String(raw || '').trim().replace(/\s+/g, '')
  const issues = []
  if (!u) {
    return {
      base: '',
      ok: false,
      issues: ['Base URL empty — set in phone CALT Sync settings'],
      host: '',
    }
  }
  if (!/^https?:\/\//i.test(u)) {
    u = `http://${u}`
    issues.push('added missing http://')
  }
  u = u.replace(/\/+$/, '')
  let host = ''
  try {
    host = u.replace(/^https?:\/\//i, '').split('/')[0]
  } catch (_) {}
  if (/localhost|127\.0\.0\.1/i.test(host)) {
    issues.push('localhost will NOT work from phone — use PC LAN IP')
  }
  return { base: u, ok: true, issues, host }
}

function errDetail(e) {
  if (e == null) return 'unknown'
  if (typeof e === 'string') return e
  try {
    if (e.message) return String(e.message)
    return JSON.stringify(e)
  } catch (_) {
    return String(e)
  }
}

function networkHint(detail, host) {
  const d = String(detail || '').toLowerCase()
  if (d.includes('network') || d.includes('-2') || d.includes('fail')) {
    return [
      `Phone cannot reach ${host || 'PC'}.`,
      '1) Same Wi‑Fi as PC',
      '2) Base URL = http://<PC-LAN-IP>:8765',
      '3) Desktop tracker running',
      '4) Open http://<IP>:8765/health in phone browser',
    ].join(' ')
  }
  return ''
}

function appendLog(entry) {
  let logs = []
  try {
    logs = JSON.parse(settingsGet('sync_log_json', '[]'))
  } catch (_) {
    logs = []
  }
  if (!Array.isArray(logs)) logs = []
  logs.unshift(entry)
  logs = logs.slice(0, MAX_LOG)
  settingsSet('sync_log_json', JSON.stringify(logs))
  settingsSet('last_sync_at', entry.at || '')
  settingsSet('last_sync_ok', entry.ok ? '1' : '0')
  settingsSet('last_sync_summary', entry.summary || '')
  settingsSet('last_sync_errors', (entry.errors || []).join(' | '))
  settingsSet('last_steps', entry.steps != null ? String(entry.steps) : '')
  settingsSet('last_sleep_min', entry.sleep_min != null ? String(entry.sleep_min) : '')
  settingsSet('last_wrote_life', entry.wrote_life ? '1' : '0')
  settingsSet('last_diag', entry.diag || '')
  settingsSet('last_url_host', entry.host || '')
  return logs
}

function authHeaders(token, withJson) {
  const h = {
    Authorization: `Bearer ${token}`,
    'X-CALT-Wearable-Key': token,
  }
  if (withJson) h['Content-Type'] = 'application/json'
  return h
}

function resolveBase() {
  const primary = normalizeBaseUrl(settingsGet('base_url', ''))
  if (primary.ok && primary.base) return primary
  const fallback = normalizeBaseUrl(settingsGet('last_good_base', ''))
  if (fallback.ok && fallback.base) {
    fallback.issues = [...(fallback.issues || []), 'using last_good_base']
    return fallback
  }
  return primary
}

async function doFetch(label, opts) {
  const url = opts.url
  try {
    const res = await fetch(opts)
    let status = res.status != null ? res.status : res.statusCode
    let body = res.body
    let parsed = null
    if (typeof body === 'string') {
      try {
        parsed = JSON.parse(body)
      } catch (_) {
        parsed = { raw: String(body).slice(0, 120) }
      }
    } else {
      parsed = body
    }
    const okHttp = status == null || (status >= 200 && status < 300)
    return {
      label,
      ok: okHttp,
      status: status != null ? status : 'n/a',
      url,
      data: parsed,
      error: null,
    }
  } catch (e) {
    return {
      label,
      ok: false,
      status: 'ERR',
      url,
      data: null,
      error: errDetail(e),
    }
  }
}

function sleepMs(ms) {
  return new Promise((resolve) => {
    if (typeof setTimeout === 'function') {
      setTimeout(resolve, ms)
      return
    }
    resolve()
  })
}

async function doFetchRetry(label, opts, attempts) {
  const n = attempts || 2
  let last = null
  for (let i = 0; i < n; i++) {
    last = await doFetch(label, opts)
    if (last.ok) return last
    await sleepMs(400 * (i + 1))
  }
  return last
}

async function pingHealth() {
  const norm = resolveBase()
  const token = String(settingsGet('ingest_token', 'calt-local-wearables'))
  const at = new Date().toISOString()
  const out = {
    ok: false,
    base: norm.base,
    host: norm.host,
    healthOk: false,
    errors: [],
    diag: '',
    at,
  }

  if (!norm.ok || !norm.base) {
    out.errors = norm.issues
    out.diag = norm.issues.join(' | ')
    appendLog({
      at,
      ok: false,
      summary: 'TEST blocked — set Base URL',
      errors: out.errors,
      steps: null,
      sleep_min: null,
      hr: null,
      wrote_life: false,
      base: '',
      host: '',
      diag: out.diag,
    })
    settingsSet('last_ping_ok', '0')
    settingsSet('last_ping_detail', out.diag)
    return out
  }

  const h = await doFetchRetry(
    'health',
    {
      url: `${norm.base}/api/wearables/zepp/health`,
      method: 'GET',
      headers: authHeaders(token, false),
    },
    2,
  )
  out.healthOk = !!(h.ok && h.data && h.data.ok)
  if (!h.ok || !out.healthOk) {
    const msg = h.error
      ? `health ${h.error}`
      : `health HTTP ${h.status}`
    out.errors.push(msg)
    const hint = networkHint(h.error || '', norm.host)
    if (hint) out.errors.push(hint)
  }

  out.ok = out.healthOk
  out.diag = [
    `host=${norm.host}`,
    `health=${out.healthOk ? 'OK' : 'FAIL'}`,
    ...(norm.issues || []),
    ...out.errors.slice(0, 2),
  ].join(' · ')

  settingsSet('last_ping_at', at)
  settingsSet('last_ping_ok', out.ok ? '1' : '0')
  settingsSet('last_ping_detail', out.diag)

  appendLog({
    at,
    ok: out.ok,
    summary: out.ok ? `TEST OK · ${norm.host}` : `TEST FAIL · ${out.errors[0] || 'error'}`,
    errors: out.errors,
    steps: null,
    sleep_min: null,
    hr: null,
    wrote_life: false,
    base: norm.base,
    host: norm.host,
    diag: out.diag,
  })
  return out
}

async function syncAll(health, opts) {
  const norm = resolveBase()
  const token = String(settingsGet('ingest_token', 'calt-local-wearables'))
  const now = new Date()
  const at = now.toISOString()
  const watchDate = String((health && health.local_date) || (opts && opts.localDate) || '')
  const resolvedDate = /^\d{4}-\d{2}-\d{2}$/.test(watchDate)
    ? watchDate
    : `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
        now.getDate(),
      ).padStart(2, '0')}`
  const tzOffset =
    health && health.tz_offset_min != null
      ? Number(health.tz_offset_min)
      : opts && opts.tz_offset_min != null
        ? Number(opts.tz_offset_min)
        : null
  const isQueued = !!(opts && opts.queuedSleepSnapshot)
  const softErrors = []
  let healthOk = false
  let wroteLife = false
  let serverEcho = null
  let duplicate = false

  const steps = health && health.activity ? health.activity.steps : null
  const sleepMain = health && health.sleep ? health.sleep.total_min : null
  const napMin = health && health.sleep ? health.sleep.nap_min || 0 : 0
  const sleepMin =
    sleepMain != null || napMin
      ? (Number(sleepMain) || 0) + (Number(napMin) || 0)
      : null
  const hr = health && health.heart ? health.heart.last : null
  const chunk = (opts && opts.chunk) || null

  if (!norm.ok || !norm.base) {
    const msg = (norm.issues || ['no base url']).join(' | ')
    appendLog({
      at,
      ok: false,
      summary: 'SEND blocked — Base URL',
      errors: [msg],
      steps,
      sleep_min: sleepMin,
      hr,
      wrote_life: false,
      base: '',
      host: '',
      diag: msg,
    })
    return {
      healthOk: false,
      wroteLife: false,
      errors: [msg],
      steps,
      sleepMin,
      hr,
      summary: msg,
      base: '',
      host: '',
      diag: msg,
      logs: [],
    }
  }

  const headers = authHeaders(token, true)

  const sleepPayload =
    health && health.sleep
      ? {
          score: health.sleep.score,
          total_min: health.sleep.total_min,
          deep_min: health.sleep.deep_min,
          start_min: health.sleep.start_min,
          end_min: health.sleep.end_min,
          stages: health.sleep.stages || [],
          naps: health.sleep.naps || [],
          nap_min: health.sleep.nap_min || 0,
          sleeping_status: health.sleep.sleeping_status,
        }
      : undefined

  const dumpId =
    (health && health.dump_id) ||
    (chunk && chunk.dump_id) ||
    `dump_${resolvedDate}_${Date.now()}`
  const chunkId =
    (chunk && chunk.chunk_id) || `${dumpId}_${(chunk && chunk.part) || 1}`
  const checksum = (health && health.checksum) || (chunk && chunk.checksum) || null

  const body = {
    schema: 2,
    source: 'mini_program',
    dump: (health && health.dump) || 'processed_v1',
    captured_at: (health && health.captured_at) || at,
    local_date: resolvedDate,
    tz_offset_min: tzOffset,
    sleep: sleepPayload,
    heart: health && health.heart ? health.heart : undefined,
    activity: health && health.activity ? health.activity : undefined,
    calorie: health && health.calorie ? health.calorie : undefined,
    distance: health && health.distance ? health.distance : undefined,
    spo2: health && health.spo2 ? health.spo2 : undefined,
    stress: health && health.stress ? health.stress : undefined,
    pai: health && health.pai ? health.pai : undefined,
    stand: health && health.stand ? health.stand : undefined,
    sitting: health && health.sitting ? health.sitting : undefined,
    battery: health && health.battery ? health.battery : undefined,
    fat_burn: health && health.fat_burn ? health.fat_burn : undefined,
    temperature: health && health.temperature ? health.temperature : undefined,
    weather: health && health.weather ? health.weather : undefined,
    meta_device: health && health.meta_device ? health.meta_device : undefined,
    capabilities: health && health.capabilities ? health.capabilities : undefined,
    device: { model: 'zepp', os: '6' },
    meta: {
      app: 'calt-zepp',
      host: norm.host,
      ver: APP_VER,
      os: 6,
      dump: (health && health.dump) || 'processed_v1',
      dump_id: dumpId,
      chunk_id: chunkId,
      checksum,
      watch_local_date: resolvedDate,
      tz_offset_min: tzOffset,
      queued_sleep_snapshot: isQueued,
      manual_dump: true,
      chunk: chunk
        ? {
            day: chunk.day || resolvedDate,
            part: chunk.part,
            total: chunk.total,
            label: chunk.label,
            dump: 'processed_v1',
            chunk_id: chunkId,
            dump_id: dumpId,
            checksum,
          }
        : undefined,
    },
  }

  const post = await doFetchRetry(
    'ingest',
    {
      url: `${norm.base}/api/wearables/zepp`,
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    },
    3,
  )
  if (post.ok && post.data && post.data.ok) {
    healthOk = true
    wroteLife = !!post.data.wrote_life_tracker
    serverEcho = post.data
    duplicate = !!(post.data.duplicate || post.data.replayed)
  } else {
    const msg = post.error ? `ingest ${post.error}` : `ingest HTTP ${post.status}`
    softErrors.push(msg)
    const hint = networkHint(post.error || '', norm.host)
    if (hint) softErrors.push(hint)
  }

  const chunkLabel = chunk && chunk.label ? `${chunk.label} ${chunk.part}/${chunk.total}` : ''
  const diag = [
    `host=${norm.host}`,
    `steps=${steps != null ? steps : '?'}`,
    `sleepMin=${sleepMin != null ? sleepMin : '?'}`,
    `ingest=${healthOk ? (duplicate ? 'DUP' : 'OK') : 'FAIL'}`,
    `life=${wroteLife ? 'yes' : 'no'}`,
    ...(norm.issues || []),
    ...softErrors.slice(0, 2),
  ]
    .filter(Boolean)
    .join(' · ')

  const summary = healthOk
    ? `${chunkLabel || 'OK'}${duplicate ? ' (replay)' : ''} →${norm.host}`
    : `FAIL ${norm.host} · ${softErrors[0] || 'error'}`

  const logs = appendLog({
    at,
    ok: healthOk,
    summary,
    errors: softErrors,
    steps,
    sleep_min: sleepMin,
    hr,
    wrote_life: wroteLife,
    base: norm.base,
    host: norm.host,
    diag,
  })

  if (healthOk && norm.host) {
    settingsSet('last_good_host', norm.host)
    settingsSet('last_good_base', norm.base)
  }

  return {
    healthOk,
    wroteLife,
    duplicate,
    replayed: duplicate,
    plans: [],
    plansFetchedAt: at,
    errors: softErrors,
    steps,
    sleepMin,
    hr,
    summary,
    base: norm.base,
    host: norm.host,
    diag,
    logs,
    localDate: resolvedDate,
    progress: chunk
      ? { part: chunk.part, total: chunk.total, label: chunk.label || '' }
      : null,
    standHours: health && health.stand ? health.stand.hours : null,
    batteryPct: health && health.battery ? health.battery.pct : null,
    serverEcho: serverEcho
      ? {
          ok: serverEcho.ok,
          wrote_life_tracker: serverEcho.wrote_life_tracker,
          local_date: serverEcho.local_date,
          applied: serverEcho.applied || null,
          duplicate: serverEcho.duplicate,
        }
      : null,
  }
}

AppSideService({
  onInit() {
    messageBuilder.listen(() => {})
    messageBuilder.on('request', (ctx) => {
      const payload = messageBuilder.buf2Json(ctx.request.payload)
      const { method, params } = payload || {}

      if (method === 'SYNC_ALL' || method === 'SYNC') {
        syncAll(params && params.health, {
          localDate: params && params.localDate,
          tz_offset_min: params && params.tz_offset_min,
          queuedSleepSnapshot: !!(params && params.queuedSleepSnapshot),
          skipFollowup: true,
          chunk: params && params.chunk,
        })
          .then((result) => ctx.response({ data: result }))
          .catch((e) =>
            ctx.response({
              data: {
                healthOk: false,
                plans: [],
                errors: [errDetail(e)],
                summary: 'fail',
                diag: errDetail(e),
                logs: [],
              },
            }),
          )
        return
      }

      if (method === 'PING' || method === 'TEST') {
        pingHealth()
          .then((result) => ctx.response({ data: result }))
          .catch((e) =>
            ctx.response({
              data: { ok: false, error: errDetail(e), diag: errDetail(e) },
            }),
          )
        return
      }

      if (method === 'GET_LOGS') {
        let logs = []
        try {
          logs = JSON.parse(settingsGet('sync_log_json', '[]'))
        } catch (_) {}
        ctx.response({
          data: {
            logs,
            base: settingsGet('base_url', ''),
            host: settingsGet('last_url_host', '') || settingsGet('last_good_host', ''),
            diag: settingsGet('last_diag', ''),
            last_summary: settingsGet('last_sync_summary', ''),
            last_errors: settingsGet('last_sync_errors', ''),
            last_good_host: settingsGet('last_good_host', ''),
          },
        })
        return
      }

      if (method === 'GET_STATUS' || method === 'GET_SETTINGS') {
        const norm = normalizeBaseUrl(settingsGet('base_url', ''))
        ctx.response({
          data: {
            base_url: norm.base || settingsGet('base_url', ''),
            host: norm.host,
            url_issues: norm.issues,
            last_sync_at: settingsGet('last_sync_at', ''),
            last_sync_summary: settingsGet('last_sync_summary', ''),
            last_diag: settingsGet('last_diag', ''),
            last_ping_ok: settingsGet('last_ping_ok', ''),
            last_ping_detail: settingsGet('last_ping_detail', ''),
            last_good_host: settingsGet('last_good_host', ''),
          },
        })
        return
      }

      ctx.response({ data: { ok: false, error: 'unknown_method' } })
    })
  },
})
