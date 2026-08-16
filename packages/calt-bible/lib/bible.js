/**
 * Load packed WEB assets one CHAPTER at a time.
 *
 * Memory rule: never read a whole book. Full-book JSON (up to 250 KB) blew the
 * watch heap and crashed the device. Chapter files are a few KB each.
 *
 * FS rule: readFileSync uses /data. Packaged JSON lives in /assets, so reads go
 * through openAssetsSync + readSync.
 * Docs: https://docs.zepp.com/docs/guides/framework/device/fs/
 */
import {
  openAssetsSync,
  readSync,
  closeSync,
  statAssetsSync,
  O_RDONLY,
} from '@zos/fs'

const MAX_ASSET_BYTES = 64 * 1024

let indexCache = null
let chapterCache = null // only the most recent chapter is kept

function utf8FromBuf(buf) {
  const u8 = buf instanceof Uint8Array ? buf : new Uint8Array(buf)
  let out = ''
  const step = 2048
  for (let i = 0; i < u8.length; i += step) {
    const end = Math.min(i + step, u8.length)
    let chunk = ''
    for (let j = i; j < end; j++) chunk += String.fromCharCode(u8[j])
    out += chunk
  }
  try {
    return decodeURIComponent(escape(out))
  } catch (_) {
    return out
  }
}

function readAssetText(path) {
  let st = null
  try {
    st = statAssetsSync({ path })
  } catch (_) {
    return null
  }
  if (!st || !st.size || st.size > MAX_ASSET_BYTES) return null

  let fd = null
  try {
    fd = openAssetsSync({ path, flag: O_RDONLY })
  } catch (_) {
    return null
  }
  if (fd == null || fd < 0) return null

  try {
    const buffer = new ArrayBuffer(st.size)
    const n = readSync({ fd, buffer })
    if (!n) return null
    return utf8FromBuf(buffer)
  } catch (_) {
    return null
  } finally {
    try {
      closeSync({ fd })
    } catch (_) {}
  }
}

function readJson(rel) {
  const paths = [`bible/${rel}`, `raw/bible/${rel}`]
  for (let i = 0; i < paths.length; i++) {
    const text = readAssetText(paths[i])
    if (!text) continue
    try {
      return JSON.parse(text)
    } catch (_) {}
  }
  return null
}

export function loadIndex() {
  if (indexCache) return indexCache
  indexCache = readJson('index.json') || { books: [] }
  return indexCache
}

export function assetsOk() {
  const idx = loadIndex()
  return !!(idx && idx.books && idx.books.length)
}

export function listBooks() {
  const idx = loadIndex()
  return (idx && idx.books) || []
}

export function bookMeta(bookId) {
  const books = listBooks()
  for (let i = 0; i < books.length; i++) {
    if (books[i].id === bookId) return books[i]
  }
  return null
}

export function bookName(bookId) {
  const meta = bookMeta(bookId)
  return meta ? meta.name : bookId
}

export function chapterCount(bookId) {
  const meta = bookMeta(bookId)
  return meta ? Number(meta.n) || 0 : 0
}

export function readChapter(bookId, chapter) {
  const id = String(bookId || 'genesis')
  const ch = Math.max(1, Number(chapter) || 1)

  if (chapterCache && chapterCache.id === id && chapterCache.chapter === ch) {
    return chapterCache
  }

  const data = readJson(`${id}/${ch}.json`)
  if (!data) {
    return {
      id,
      name: bookName(id) || id,
      chapter: ch,
      verses: [],
      missing: true,
    }
  }

  chapterCache = {
    id,
    name: data.name || bookName(id),
    chapter: ch,
    verses: data.v || [],
    missing: false,
  }
  return chapterCache
}

export function chapterVerseCount(bookId, chapter) {
  return readChapter(bookId, chapter).verses || []
}

/**
 * Next chapter in the Genesis → Revelation plan, computed from the index.
 */
export function nextPlanEntry(bookId, chapter) {
  const books = listBooks()
  const ch = Number(chapter) || 1
  for (let i = 0; i < books.length; i++) {
    if (books[i].id !== bookId) continue
    if (ch < Number(books[i].n || 0)) return { b: bookId, c: ch + 1 }
    const nxt = books[i + 1]
    return nxt ? { b: nxt.id, c: 1 } : null
  }
  return null
}
