/**
 * Side Service — relays voice-note chunks from the watch to the tracker hub.
 *
 * Deliberately dumb: it forwards what the watch sends and returns what the hub
 * answers. All integrity decisions (checksums, resume, when it is safe to
 * delete the local file) live on the watch and the hub, so a bug here can
 * stall a transfer but cannot corrupt one.
 */
import { MessageBuilder } from '../shared/message-side'

const messageBuilder = new MessageBuilder()

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
  if (d.includes('network') || d.includes('-2') || d.includes('fail') || d.includes('unreachable')) {
    return [
      `Phone cannot reach ${host || 'PC'}.`,
      'Same Wi-Fi as PC',
      'Base URL = http://<PC-LAN-IP>:8765',
      'Desktop tracker running',
    ].join(' ')
  }
  return ''
}

function parseBody(res) {
  const body = res.body
  if (body == null || body === '') return null
  if (typeof body === 'object') return body
  try {
    return JSON.parse(String(body))
  } catch (_) {
    return { raw: String(body).slice(0, 120) }
  }
}

function normalizeBaseUrl(raw) {
  let u = String(raw || '').trim().replace(/\s+/g, '')
  const issues = []
  if (!u) return { base: '', ok: false, issues: ['Base URL empty — set in phone settings'], host: '' }
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

function authHeaders(withJson) {
  const token = String(settingsGet('ingest_token', 'calt-local-wearables'))
  const h = { Authorization: `Bearer ${token}`, 'X-CALT-Wearable-Key': token }
  if (withJson) h['Content-Type'] = 'application/json'
  return h
}

/**
 * Ordered receivers. Index 0 is the desktop hub; index 1 is an optional
 * always-on fallback for when the PC is off.
 *
 * The index matters: an upload is stateful (begin/chunk/finish), so the watch
 * pins whichever index answered VN_BEGIN and passes it back on every later
 * call. Without that pinning a mid-transfer failover would scatter chunks
 * across two receivers and each would fail its whole-file hash.
 */
function destinations() {
  const out = []
  const keys = ['base_url', 'fallback_url']
  for (let i = 0; i < keys.length; i++) {
    const raw = settingsGet(keys[i], '')
    if (!String(raw).trim()) continue
    const norm = normalizeBaseUrl(raw)
    if (norm.ok && norm.base) out.push({ index: i, base: norm.base, host: norm.host, issues: norm.issues })
  }
  return out
}

function sleepMs(ms) {
  return new Promise((resolve) => {
    if (typeof setTimeout === 'function') setTimeout(resolve, ms)
    else resolve()
  })
}

/** One receiver, with retries. Never fails over — that is the caller's job. */
async function callOne(dest, path, method, payload, attempts) {
  const opts = {
    url: `${dest.base}${path}`,
    method,
    headers: authHeaders(method === 'POST'),
  }
  if (method === 'POST') opts.body = JSON.stringify(payload || {})

  const tries = attempts || 3
  let last = null
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(opts)
      const status = res.status != null ? res.status : res.statusCode
      const parsed = parseBody(res)
      if (status == null || (status >= 200 && status < 300)) {
        settingsSet('last_note_host', dest.host)
        if (dest.index === 0 && dest.base) {
          settingsSet('last_good_base', dest.base)
        }
        return { ok: true, status, data: parsed, host: dest.host, dest: dest.index }
      }
      const errMsg = (parsed && parsed.error) || `HTTP ${status}`
      last = { ok: false, status, data: parsed, error: errMsg, host: dest.host, dest: dest.index }
      if (status >= 400 && status < 500) return last
    } catch (e) {
      const detail = errDetail(e)
      const hint = networkHint(detail, dest.host)
      last = {
        ok: false,
        error: hint ? `${detail} · ${hint}` : detail,
        host: dest.host,
        dest: dest.index,
      }
    }
    await sleepMs(400 * (i + 1))
  }
  return last || { ok: false, error: 'unreachable', host: dest.host, dest: dest.index }
}

/**
 * `pinned` selects an exact receiver (mid-transfer calls). When it is null the
 * receivers are tried in order, which only ever happens on VN_BEGIN/VN_PING.
 */
async function callHub(path, method, payload, attempts, pinned) {
  const all = destinations()
  if (!all.length) {
    return { ok: false, error: 'No Base URL — set it in the Zepp app settings', host: '' }
  }

  if (pinned !== null && pinned !== undefined) {
    const only = all.filter((d) => d.index === Number(pinned))
    if (!only.length) {
      return { ok: false, error: `destination ${pinned} is no longer configured`, host: '' }
    }
    return callOne(only[0], path, method, payload, attempts)
  }

  let last = null
  for (let i = 0; i < all.length; i++) {
    const res = await callOne(all[i], path, method, payload, attempts)
    if (res.ok) return res
    // A 4xx is a verdict on the payload, not on reachability — failing over
    // would just get the same rejection from a second receiver.
    if (res.status && res.status >= 400 && res.status < 500) return res
    last = res
  }
  return last
}

AppSideService({
  onInit() {
    messageBuilder.listen(() => {})
    messageBuilder.on('request', (ctx) => {
      const payload = messageBuilder.buf2Json(ctx.request.payload)
      const { method, params } = payload || {}
      const p = params || {}

      const reply = (promise) =>
        promise
          .then((r) => ctx.response({ data: r }))
          .catch((e) => ctx.response({ data: { ok: false, error: errDetail(e) } }))

      // `dest` is routing state for this relay; the hub never sees it.
      const pinned = p.dest === undefined || p.dest === null ? null : Number(p.dest)
      const body = {}
      Object.keys(p).forEach((k) => {
        if (k !== 'dest') body[k] = p[k]
      })

      if (method === 'VN_BEGIN') {
        // Unpinned: picks a receiver and reports which one in `dest`.
        reply(callHub('/api/hub/voice-note/begin', 'POST', body, 3, null))
        return
      }
      if (method === 'VN_CHUNK') {
        reply(callHub('/api/hub/voice-note/chunk', 'POST', body, 3, pinned))
        return
      }
      if (method === 'VN_FINISH') {
        reply(callHub('/api/hub/voice-note/finish', 'POST', body, 3, pinned))
        return
      }
      if (method === 'VN_PING') {
        reply(callHub('/health', 'GET', null, 2, pinned))
        return
      }

      ctx.response({ data: { ok: false, error: 'unknown_method' } })
    })
  },
})
