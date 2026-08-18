/**
 * Plan state for daily chapter + verse notifications.
 */
import { localStorage } from '@zos/storage'
import { Time } from '@zos/sensor'
import { nextPlanEntry, bookName, chapterVerseCount } from './bible'

const KEY = 'calt_bible_plan'

export function todayKey() {
  const d = new Date()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export function hourStamp(hour) {
  const d = new Date()
  let h = hour
  if (h == null || Number.isNaN(Number(h))) {
    try {
      h = new Time().getHours()
    } catch (_) {
      try {
        h = d.getHours()
      } catch (__) {
        h = 0
      }
    }
  }
  h = Math.max(0, Math.min(23, Number(h) || 0))
  return `${todayKey()}T${h < 10 ? '0' : ''}${h}`
}

function addDays(key, n) {
  const parts = String(key || '').split('-')
  if (parts.length !== 3) return todayKey()
  const dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
  dt.setDate(dt.getDate() + n)
  const m = `${dt.getMonth() + 1}`.padStart(2, '0')
  const day = `${dt.getDate()}`.padStart(2, '0')
  return `${dt.getFullYear()}-${m}-${day}`
}

function defaults() {
  return {
    current_book: 'genesis',
    current_chapter: 1,
    verse_cursor: 0,
    plan_day: '',
    notify_mode: 'hourly',
    plan_complete: false,
    notify_hour_key: '',
  }
}

export function loadPlan() {
  const base = defaults()
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (raw && typeof raw === 'object') {
      Object.keys(base).forEach((k) => {
        if (raw[k] != null) base[k] = raw[k]
      })
    }
  } catch (_) {}
  return base
}

export function savePlan(plan) {
  try {
    localStorage.setItem(KEY, JSON.stringify(plan))
  } catch (_) {}
  return plan
}

export function setCurrentChapter(bookId, chapter) {
  const plan = loadPlan()
  plan.current_book = String(bookId || 'genesis')
  plan.current_chapter = Math.max(1, Number(chapter) || 1)
  plan.verse_cursor = 0
  plan.plan_complete = false
  plan.plan_day = todayKey()
  return savePlan(plan)
}

export function setNotifyMode(mode) {
  const plan = loadPlan()
  plan.notify_mode = mode === 'off' ? 'off' : 'hourly'
  return savePlan(plan)
}

export function chapterLabel(plan) {
  const name = bookName(plan.current_book) || plan.current_book
  return `${name} ${plan.current_chapter}`
}

export function nextChapterLabel(plan) {
  if (plan.plan_complete) return 'Plan complete'
  const nxt = nextPlanEntry(plan.current_book, plan.current_chapter)
  if (!nxt) return 'Plan complete'
  const name = bookName(nxt.b) || nxt.b
  return `${name} ${nxt.c}`
}

/**
 * Advance one chapter per missed local day. First launch stamps today without advancing.
 */
export function ensurePlanDay() {
  const plan = loadPlan()
  const today = todayKey()
  if (!plan.plan_day) {
    plan.plan_day = today
    return savePlan(plan)
  }
  if (plan.plan_complete) {
    if (plan.plan_day !== today) {
      plan.plan_day = today
      return savePlan(plan)
    }
    return plan
  }
  if (plan.plan_day === today) return plan
  if (plan.plan_day > today) {
    plan.plan_day = today
    return savePlan(plan)
  }

  let day = plan.plan_day
  let guard = 0
  while (day < today && guard < 14) {
    const nxt = nextPlanEntry(plan.current_book, plan.current_chapter)
    if (!nxt) {
      plan.plan_complete = true
      break
    }
    plan.current_book = nxt.b
    plan.current_chapter = nxt.c
    plan.verse_cursor = 0
    day = addDays(day, 1)
    guard += 1
    if (!nextPlanEntry(plan.current_book, plan.current_chapter)) {
      plan.plan_complete = true
      break
    }
  }
  plan.plan_day = today
  return savePlan(plan)
}

export function takeNotifyVerse() {
  const plan = ensurePlanDay()
  if (plan.notify_mode !== 'hourly') return null
  const verses = chapterVerseCount(plan.current_book, plan.current_chapter)
  if (!verses || !verses.length) return null
  let i = Number(plan.verse_cursor) || 0
  if (i < 0 || i >= verses.length) i = 0
  const v = verses[i]
  plan.verse_cursor = (i + 1) % verses.length
  savePlan(plan)
  const name = bookName(plan.current_book) || plan.current_book
  return {
    ref: `${name} ${plan.current_chapter}:${v.n}`,
    text: v.t,
    index: i,
    total: verses.length,
  }
}

export function markNotifyHour(hourKey) {
  const plan = loadPlan()
  plan.notify_hour_key = hourKey
  savePlan(plan)
}
