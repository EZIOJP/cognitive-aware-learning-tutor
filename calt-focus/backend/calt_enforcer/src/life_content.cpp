#include "life_content.h"
#include "productivity_store.h"
#include "softland_publish.h"
#include "sqlite3.h"

#include <windows.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

// gDb declared in productivity_store.h

namespace {

std::string EscapeJson(const std::string& s) {
  std::string o;
  o.reserve(s.size() + 8);
  for (char c : s) {
    switch (c) {
      case '"':
        o += "\\\"";
        break;
      case '\\':
        o += "\\\\";
        break;
      case '\n':
        o += "\\n";
        break;
      case '\r':
        o += "\\r";
        break;
      case '\t':
        o += "\\t";
        break;
      default:
        o.push_back(c);
    }
  }
  return o;
}

std::string LocalDateYmd() { return ProductivityLocalDate(); }

std::string IsoNow() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u", st.wYear, st.wMonth, st.wDay, st.wHour,
           st.wMinute, st.wSecond);
  return buf;
}

bool JsonGetStringLocal(const std::string& body, const char* key, std::string* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t')) ++i;
  if (i >= body.size() || body[i] != '"') return false;
  ++i;
  std::string val;
  while (i < body.size() && body[i] != '"') {
    if (body[i] == '\\' && i + 1 < body.size()) {
      val.push_back(body[i + 1]);
      i += 2;
      continue;
    }
    val.push_back(body[i++]);
  }
  *out = val;
  return true;
}

bool JsonGetIntLocal(const std::string& body, const char* key, int* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t')) ++i;
  if (i >= body.size()) return false;
  *out = atoi(body.c_str() + i);
  return true;
}

std::string ReadFileUtf8(const std::wstring& path) {
  HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                         FILE_ATTRIBUTE_NORMAL, nullptr);
  if (h == INVALID_HANDLE_VALUE) return {};
  LARGE_INTEGER sz{};
  if (!GetFileSizeEx(h, &sz) || sz.QuadPart <= 0 || sz.QuadPart > 8 * 1024 * 1024) {
    CloseHandle(h);
    return {};
  }
  std::string out(static_cast<size_t>(sz.QuadPart), '\0');
  DWORD n = 0;
  BOOL ok = ReadFile(h, out.data(), static_cast<DWORD>(out.size()), &n, nullptr);
  CloseHandle(h);
  if (!ok) return {};
  out.resize(n);
  return out;
}

struct PlanChapter {
  std::string book;
  int chapter = 1;
};

std::vector<PlanChapter> LoadPlan(const std::wstring& bibleDataDir) {
  std::vector<PlanChapter> plan;
  std::string body = ReadFileUtf8(bibleDataDir + L"\\chapter_index.json");
  if (body.empty()) {
    plan.push_back({"Genesis", 1});
    return plan;
  }
  // Naive scan: "book":"...","chapter":N
  size_t i = 0;
  while (i < body.size()) {
    size_t b = body.find("\"book\"", i);
    if (b == std::string::npos) break;
    std::string book;
    int ch = 0;
    if (!JsonGetStringLocal(body.substr(b), "book", &book)) {
      i = b + 6;
      continue;
    }
    size_t cpos = body.find("\"chapter\"", b);
    if (cpos == std::string::npos || cpos > b + 200) {
      i = b + 6;
      continue;
    }
    JsonGetIntLocal(body.substr(cpos), "chapter", &ch);
    if (!book.empty() && ch > 0) plan.push_back({book, ch});
    i = b + 6;
  }
  if (plan.empty()) plan.push_back({"Genesis", 1});
  return plan;
}

std::string ChapterKey(const std::string& book, int chapter) {
  return book + "|" + std::to_string(chapter);
}

bool LoadDayRow(int userId, const std::string& day, std::string* docOut) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  const char* sql =
      "SELECT document_json FROM productivity_bible_day WHERE user_id=? AND day=? LIMIT 1;";
  if (sqlite3_prepare_v2(gDb, sql, -1, &st, nullptr) != SQLITE_OK) return false;
  sqlite3_bind_int(st, 1, userId);
  sqlite3_bind_text(st, 2, day.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = false;
  if (sqlite3_step(st) == SQLITE_ROW) {
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(st, 0));
    if (t && docOut) *docOut = t;
    ok = true;
  }
  sqlite3_finalize(st);
  return ok;
}

bool SaveDayRow(int userId, const std::string& day, const std::string& doc) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  const char* sql =
      "INSERT INTO productivity_bible_day(user_id, day, document_json, updated_at) VALUES(?,?,?,?) "
      "ON CONFLICT(user_id, day) DO UPDATE SET document_json=excluded.document_json, "
      "updated_at=excluded.updated_at;";
  if (sqlite3_prepare_v2(gDb, sql, -1, &st, nullptr) != SQLITE_OK) return false;
  std::string now = IsoNow();
  sqlite3_bind_int(st, 1, userId);
  sqlite3_bind_text(st, 2, day.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, doc.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::string EmptyDayDoc(const std::string& day, const PlanChapter& assigned) {
  return std::string("{\"day\":\"") + day + "\",\"bible_seconds\":0,\"chapters_completed\":[],"
         "\"assigned_book\":\"" + EscapeJson(assigned.book) + "\",\"assigned_chapter\":" +
         std::to_string(assigned.chapter) + ",\"devotion\":{},\"last_heartbeat_at\":0}";
}

bool PublishBibleDone(bool done, const std::wstring& behaviorDir) {
  ProductivitySoftland s;
  if (!ProductivityLoadSoftland(s)) return false;
  std::string needle = "\"goals\"";
  size_t p = s.document_json.find(needle);
  if (p == std::string::npos) return false;
  size_t brace = s.document_json.find('{', p);
  if (brace == std::string::npos) return false;
  int depth = 0;
  size_t end = brace;
  for (; end < s.document_json.size(); ++end) {
    if (s.document_json[end] == '{') ++depth;
    else if (s.document_json[end] == '}') {
      --depth;
      if (depth == 0) {
        ++end;
        break;
      }
    }
  }
  std::string goalsObj = s.document_json.substr(brace, end - brace);
  if (!ProductivityReplaceJsonValue(goalsObj, "bible_done", done ? "true" : "false")) {
    if (goalsObj.size() > 2) {
      goalsObj.insert(goalsObj.size() - 1,
                      std::string(",\"bible_done\":") + (done ? "true" : "false"));
    }
  }
  if (!ProductivityReplaceJsonValue(s.document_json, "goals", goalsObj)) return false;
  if (!ProductivitySaveSoftland(s)) return false;
  PublishSoftlandMirror(behaviorDir, s);
  ProductivityBumpSeq();
  return true;
}

int CountCompleted(const std::string& doc) {
  size_t p = doc.find("\"chapters_completed\"");
  if (p == std::string::npos) return 0;
  size_t a = doc.find('[', p);
  size_t b = doc.find(']', a);
  if (a == std::string::npos || b == std::string::npos || b <= a) return 0;
  std::string arr = doc.substr(a, b - a + 1);
  int n = 0;
  for (size_t i = 0; i + 1 < arr.size(); ++i) {
    if (arr[i] == '"' && arr[i + 1] != ',' && arr[i + 1] != ']') {
      // start of string
      size_t j = i + 1;
      while (j < arr.size() && arr[j] != '"') {
        if (arr[j] == '\\') ++j;
        ++j;
      }
      if (j < arr.size()) ++n;
      i = j;
    }
  }
  return n;
}

bool ChaptersCompletedHas(const std::string& doc, const std::string& key) {
  size_t p = doc.find("\"chapters_completed\"");
  if (p == std::string::npos) return false;
  size_t a = doc.find('[', p);
  size_t b = doc.find(']', a);
  if (a == std::string::npos || b == std::string::npos) return false;
  return doc.substr(a, b - a + 1).find("\"" + key + "\"") != std::string::npos;
}

std::string BuildStateJson(const std::string& doc, const PlanChapter& assigned) {
  std::string day = LocalDateYmd();
  JsonGetStringLocal(doc, "day", &day);
  int secs = 0;
  JsonGetIntLocal(doc, "bible_seconds", &secs);
  std::string key = ChapterKey(assigned.book, assigned.chapter);
  bool done = ChaptersCompletedHas(doc, key);
  int completed = CountCompleted(doc);
  bool met = completed >= 1;
  std::string chaptersArr = done ? (std::string("[\"") + EscapeJson(key) + "\"]") : "[]";
  return std::string("{\"day\":\"") + EscapeJson(day) + "\",\"bible_minutes\":" +
         std::to_string(secs / 60.0) + ",\"bible_seconds\":" + std::to_string(secs) +
         ",\"game_bank_remaining_minutes\":0,\"game_bank_remaining_seconds\":0,"
         "\"last_page\":1,\"bookmarks\":[],\"today_chapter\":{\"book\":\"" +
         EscapeJson(assigned.book) + "\",\"chapter\":" + std::to_string(assigned.chapter) +
         ",\"key\":\"" + EscapeJson(key) + "\",\"label\":\"" + EscapeJson(assigned.book) + " " +
         std::to_string(assigned.chapter) + "\",\"done\":" + (done ? "true" : "false") +
         ",\"mode\":\"today_only\"},\"chapter_goal\":{\"done\":" + std::to_string(completed) +
         ",\"target\":1,\"met\":" + (met ? "true" : "false") + "},\"chapters_completed_today\":" +
         chaptersArr + "}";
}

PlanChapter AssignedFromDoc(const std::string& doc, const std::vector<PlanChapter>& plan) {
  std::string book;
  int ch = 1;
  if (JsonGetStringLocal(doc, "assigned_book", &book) && JsonGetIntLocal(doc, "assigned_chapter", &ch) &&
      !book.empty() && ch > 0) {
    return {book, ch};
  }
  return plan.empty() ? PlanChapter{"Genesis", 1} : plan[0];
}

int DayOfYear() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  // Approximate: month days
  static const int mdays[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  int d = st.wDay;
  for (int m = 1; m < st.wMonth; ++m) d += mdays[m];
  // leap
  if (st.wMonth > 2) {
    int y = st.wYear;
    if ((y % 4 == 0 && y % 100 != 0) || (y % 400 == 0)) ++d;
  }
  return d;
}

}  // namespace

void LifeEnsureTables() {
  if (!gDb) return;
  sqlite3_exec(gDb,
               "CREATE TABLE IF NOT EXISTS productivity_journal ("
               "  id INTEGER PRIMARY KEY,"
               "  user_id INTEGER NOT NULL,"
               "  entry_date TEXT NOT NULL,"
               "  title TEXT,"
               "  content TEXT NOT NULL,"
               "  created_at TEXT,"
               "  updated_at TEXT"
               ");"
               "CREATE INDEX IF NOT EXISTS ix_prod_journal_user_date "
               "  ON productivity_journal(user_id, entry_date);"
               "CREATE TABLE IF NOT EXISTS productivity_bible_day ("
               "  user_id INTEGER NOT NULL,"
               "  day TEXT NOT NULL,"
               "  document_json TEXT NOT NULL,"
               "  updated_at TEXT NOT NULL,"
               "  PRIMARY KEY (user_id, day)"
               ");",
               nullptr, nullptr, nullptr);
}

std::string LifeJournalSummaryJson(const std::string& dayYmd, int userId) {
  LifeEnsureTables();
  std::string day = dayYmd.empty() ? LocalDateYmd() : dayYmd;
  if (!gDb) {
    return std::string("{\"day\":\"") + day + "\",\"journal_written\":false,\"journal_entry\":null}";
  }
  sqlite3_stmt* st = nullptr;
  const char* sql =
      "SELECT id, entry_date, title, content, updated_at FROM productivity_journal "
      "WHERE user_id=? AND entry_date=? ORDER BY id DESC LIMIT 1;";
  if (sqlite3_prepare_v2(gDb, sql, -1, &st, nullptr) != SQLITE_OK) {
    return std::string("{\"day\":\"") + day + "\",\"journal_written\":false,\"journal_entry\":null}";
  }
  sqlite3_bind_int(st, 1, userId);
  sqlite3_bind_text(st, 2, day.c_str(), -1, SQLITE_TRANSIENT);
  std::string out;
  if (sqlite3_step(st) == SQLITE_ROW) {
    long long id = sqlite3_column_int64(st, 0);
    const char* ed = reinterpret_cast<const char*>(sqlite3_column_text(st, 1));
    const char* title = reinterpret_cast<const char*>(sqlite3_column_text(st, 2));
    const char* content = reinterpret_cast<const char*>(sqlite3_column_text(st, 3));
    const char* updated = reinterpret_cast<const char*>(sqlite3_column_text(st, 4));
    out = std::string("{\"day\":\"") + day + "\",\"journal_written\":true,\"journal_entry\":{"
          "\"id\":" + std::to_string(id) + ",\"entry_date\":\"" + EscapeJson(ed ? ed : day) +
          "\",\"title\":" + (title ? ("\"" + EscapeJson(title) + "\"") : "null") +
          ",\"content\":\"" + EscapeJson(content ? content : "") + "\",\"updated_at\":" +
          (updated ? ("\"" + EscapeJson(updated) + "\"") : "null") + "}}";
  } else {
    out = std::string("{\"day\":\"") + day + "\",\"journal_written\":false,\"journal_entry\":null}";
  }
  sqlite3_finalize(st);
  return out;
}

std::string LifeJournalLogJson(int limit, int userId) {
  LifeEnsureTables();
  if (limit <= 0) limit = 30;
  if (limit > 200) limit = 200;
  if (!gDb) return "[]";
  sqlite3_stmt* st = nullptr;
  const char* sql =
      "SELECT id, entry_date, title, updated_at, content FROM productivity_journal "
      "WHERE user_id=? ORDER BY entry_date DESC, id DESC LIMIT ?;";
  if (sqlite3_prepare_v2(gDb, sql, -1, &st, nullptr) != SQLITE_OK) return "[]";
  sqlite3_bind_int(st, 1, userId);
  sqlite3_bind_int(st, 2, limit);
  std::string arr = "[";
  bool first = true;
  while (sqlite3_step(st) == SQLITE_ROW) {
    long long id = sqlite3_column_int64(st, 0);
    const char* ed = reinterpret_cast<const char*>(sqlite3_column_text(st, 1));
    const char* title = reinterpret_cast<const char*>(sqlite3_column_text(st, 2));
    const char* updated = reinterpret_cast<const char*>(sqlite3_column_text(st, 3));
    const char* content = reinterpret_cast<const char*>(sqlite3_column_text(st, 4));
    std::string c = content ? content : "";
    int words = 0;
    bool in = false;
    for (char ch : c) {
      if (ch == ' ' || ch == '\n' || ch == '\t')
        in = false;
      else if (!in) {
        in = true;
        ++words;
      }
    }
    if (!first) arr += ",";
    first = false;
    arr += "{\"id\":" + std::to_string(id) + ",\"entry_date\":\"" + EscapeJson(ed ? ed : "") +
           "\",\"title\":" + (title ? ("\"" + EscapeJson(title) + "\"") : "null") +
           ",\"updated_at\":" + (updated ? ("\"" + EscapeJson(updated) + "\"") : "null") +
           ",\"content_length\":" + std::to_string((int)c.size()) + ",\"word_count\":" +
           std::to_string(words) + "}";
  }
  sqlite3_finalize(st);
  arr += "]";
  return arr;
}

bool LifeJournalUpsert(const std::string& payloadJson, int userId, std::string* outEntryJson) {
  LifeEnsureTables();
  if (!gDb) return false;
  std::string content, title, entryDate;
  if (!JsonGetStringLocal(payloadJson, "content", &content)) return false;
  JsonGetStringLocal(payloadJson, "title", &title);
  if (!JsonGetStringLocal(payloadJson, "entry_date", &entryDate) || entryDate.empty())
    entryDate = LocalDateYmd();
  std::string now = IsoNow();

  // Update today's latest row if exists
  sqlite3_stmt* find = nullptr;
  long long existingId = 0;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT id FROM productivity_journal WHERE user_id=? AND entry_date=? "
                         "ORDER BY id DESC LIMIT 1;",
                         -1, &find, nullptr) == SQLITE_OK) {
    sqlite3_bind_int(find, 1, userId);
    sqlite3_bind_text(find, 2, entryDate.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(find) == SQLITE_ROW) existingId = sqlite3_column_int64(find, 0);
    sqlite3_finalize(find);
  }

  if (existingId > 0) {
    sqlite3_stmt* st = nullptr;
    if (sqlite3_prepare_v2(gDb,
                           "UPDATE productivity_journal SET title=?, content=?, updated_at=? WHERE id=?;",
                           -1, &st, nullptr) != SQLITE_OK)
      return false;
    sqlite3_bind_text(st, 1, title.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 2, content.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(st, 4, existingId);
    bool ok = sqlite3_step(st) == SQLITE_DONE;
    sqlite3_finalize(st);
    if (!ok) return false;
    if (outEntryJson) {
      *outEntryJson = "{\"id\":" + std::to_string(existingId) + ",\"entry_date\":\"" +
                      EscapeJson(entryDate) + "\",\"title\":\"" + EscapeJson(title) +
                      "\",\"content\":\"" + EscapeJson(content) + "\",\"updated_at\":\"" +
                      EscapeJson(now) + "\"}";
    }
    return true;
  }

  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT INTO productivity_journal(user_id, entry_date, title, content, "
                         "created_at, updated_at) VALUES(?,?,?,?,?,?);",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_int(st, 1, userId);
  sqlite3_bind_text(st, 2, entryDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, title.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, content.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 5, now.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 6, now.c_str(), -1, SQLITE_TRANSIENT);
  int rc = sqlite3_step(st);
  long long newId = sqlite3_last_insert_rowid(gDb);
  if (rc != SQLITE_DONE) {
    sqlite3_finalize(st);
    return false;
  }
  sqlite3_finalize(st);
  if (outEntryJson) {
    *outEntryJson = "{\"id\":" + std::to_string(newId) + ",\"entry_date\":\"" + EscapeJson(entryDate) +
                    "\",\"title\":\"" + EscapeJson(title) + "\",\"content\":\"" + EscapeJson(content) +
                    "\",\"updated_at\":\"" + EscapeJson(now) + "\"}";
  }
  return true;
}

void LifeBibleEnsureToday(int userId, const std::wstring& bibleDataDir) {
  LifeEnsureTables();
  std::string day = LocalDateYmd();
  std::string doc;
  if (LoadDayRow(userId, day, &doc)) return;
  auto plan = LoadPlan(bibleDataDir);
  // Import legacy JSON if present
  std::wstring legacy = bibleDataDir + L"\\day_" + std::to_wstring(userId) + L"_" +
                        std::wstring(day.begin(), day.end()) + L".json";
  std::string legacyBody = ReadFileUtf8(legacy);
  PlanChapter assigned = plan.empty() ? PlanChapter{"Genesis", 1} : plan[0];
  if (!legacyBody.empty()) {
    doc = legacyBody;
    std::string ab;
    int ac = 0;
    if (JsonGetStringLocal(doc, "assigned_book", &ab) && JsonGetIntLocal(doc, "assigned_chapter", &ac)) {
      assigned = {ab, ac};
    }
  } else {
    // Advance from lifetime: pick first plan chapter not done — simplified: use plan[0] or
    // cursor from reader — keep simple: Genesis→… by day-of-year index
    int idx = (DayOfYear() - 1) % static_cast<int>(plan.size());
    assigned = plan[idx];
    doc = EmptyDayDoc(day, assigned);
  }
  SaveDayRow(userId, day, doc);
}

std::string LifeBibleStateJson(int userId, const std::wstring& bibleDataDir) {
  LifeBibleEnsureToday(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  LoadDayRow(userId, day, &doc);
  auto plan = LoadPlan(bibleDataDir);
  PlanChapter assigned = AssignedFromDoc(doc, plan);
  return BuildStateJson(doc, assigned);
}

std::string LifeBibleTodayJson(int userId, const std::wstring& bibleDataDir) {
  // Same as state — chapter body filled by Focus corpus loader
  return LifeBibleStateJson(userId, bibleDataDir);
}

bool LifeBibleTick(int userId, const std::string& book, int chapter, bool done,
                   const std::wstring& bibleDataDir, const std::wstring& behaviorDir,
                   std::string* outStateJson) {
  LifeBibleEnsureToday(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  if (!LoadDayRow(userId, day, &doc)) return false;
  auto plan = LoadPlan(bibleDataDir);
  PlanChapter assigned = AssignedFromDoc(doc, plan);
  std::string key = ChapterKey(assigned.book, assigned.chapter);
  std::string want = ChapterKey(book, chapter);
  if (want != key && !book.empty()) {
    // Only assigned chapter ticks morning goal
    if (outStateJson) *outStateJson = BuildStateJson(doc, assigned);
    return false;
  }
  // Rewrite chapters_completed
  if (done) {
    if (!ChaptersCompletedHas(doc, key)) {
      size_t p = doc.find("\"chapters_completed\"");
      if (p != std::string::npos) {
        size_t a = doc.find('[', p);
        size_t b = doc.find(']', a);
        if (a != std::string::npos && b != std::string::npos) {
          std::string arr = doc.substr(a, b - a + 1);
          if (arr == "[]")
            arr = "[\"" + EscapeJson(key) + "\"]";
          else
            arr = arr.substr(0, arr.size() - 1) + ",\"" + EscapeJson(key) + "\"]";
          doc.replace(a, b - a + 1, arr);
        }
      }
    }
  } else {
    // remove key — crude
    std::string needle = "\"" + key + "\"";
    size_t p = doc.find(needle);
    if (p != std::string::npos) {
      doc.erase(p, needle.size());
      // clean commas
      size_t cc = doc.find("\"chapters_completed\"");
      if (cc != std::string::npos) {
        size_t a = doc.find('[', cc);
        size_t b = doc.find(']', a);
        if (a != std::string::npos && b != std::string::npos) {
          std::string arr = doc.substr(a, b - a + 1);
          // collapse ,, and [, and ,]
          while (arr.find(",,") != std::string::npos) {
            size_t x = arr.find(",,");
            arr.replace(x, 2, ",");
          }
          if (arr.find("[,") == 0) arr.replace(1, 1, "");
          if (arr.size() >= 2 && arr[arr.size() - 2] == ',') arr.erase(arr.size() - 2, 1);
          if (arr == "[,]" || arr == "[, ]") arr = "[]";
          doc.replace(a, b - a + 1, arr);
        }
      }
    }
  }
  if (!SaveDayRow(userId, day, doc)) return false;
  bool met = done ? true : (CountCompleted(doc) >= 1);
  if (done) met = true;
  // Recompute from chapters_completed after rewrite
  met = CountCompleted(doc) >= 1 || (done && ChaptersCompletedHas(doc, key));
  PublishBibleDone(done ? true : met, behaviorDir);
  if (outStateJson) *outStateJson = BuildStateJson(doc, assigned);
  return true;
}

bool LifeBibleHeartbeat(int userId, const std::string& book, int chapter, bool focused,
                        const std::wstring& bibleDataDir, std::string* outStateJson) {
  LifeBibleEnsureToday(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  if (!LoadDayRow(userId, day, &doc)) return false;
  auto plan = LoadPlan(bibleDataDir);
  PlanChapter assigned = AssignedFromDoc(doc, plan);
  if (ChapterKey(book, chapter) != ChapterKey(assigned.book, assigned.chapter)) {
    if (outStateJson) *outStateJson = BuildStateJson(doc, assigned);
    return true;
  }
  if (focused) {
    int secs = 0;
    JsonGetIntLocal(doc, "bible_seconds", &secs);
    secs += 25;
    // replace bible_seconds value
    size_t p = doc.find("\"bible_seconds\"");
    if (p != std::string::npos) {
      size_t colon = doc.find(':', p);
      size_t i = colon + 1;
      while (i < doc.size() && (doc[i] == ' ' || doc[i] == '\t')) ++i;
      size_t j = i;
      while (j < doc.size() && (isdigit((unsigned char)doc[j]) || doc[j] == '-')) ++j;
      doc.replace(i, j - i, std::to_string(secs));
    }
  }
  SaveDayRow(userId, day, doc);
  if (outStateJson) *outStateJson = BuildStateJson(doc, assigned);
  return true;
}

std::string LifeBibleDevotionTodayJson(int userId, const std::wstring& bibleDataDir) {
  std::string state = LifeBibleStateJson(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  LoadDayRow(userId, day, &doc);
  int doy = DayOfYear();
  int prov = (doy % 31) + 1;
  int psalm = (doy % 150) + 1;
  std::string aftKey = "Proverbs|" + std::to_string(prov);
  std::string eveKey = "Psalms|" + std::to_string(psalm);
  bool aftDone = doc.find("\"afternoon_done\":true") != std::string::npos;
  bool eveDone = doc.find("\"evening_done\":true") != std::string::npos;
  // Merge devotion shell into state-like devotion payload
  return std::string("{") +
         "\"day\":\"" + day + "\"," +
         "\"today_chapter\":" + [&]() {
           size_t p = state.find("\"today_chapter\"");
           if (p == std::string::npos) return std::string("null");
           size_t b = state.find('{', p);
           int depth = 0;
           size_t e = b;
           for (; e < state.size(); ++e) {
             if (state[e] == '{') ++depth;
             else if (state[e] == '}') {
               --depth;
               if (depth == 0) {
                 ++e;
                 break;
               }
             }
           }
           return state.substr(b, e - b);
         }() +
         ",\"chapter_goal\":" + [&]() {
           size_t p = state.find("\"chapter_goal\"");
           if (p == std::string::npos) return std::string("{\"done\":0,\"target\":1,\"met\":false}");
           size_t b = state.find('{', p);
           int depth = 0;
           size_t e = b;
           for (; e < state.size(); ++e) {
             if (state[e] == '{') ++depth;
             else if (state[e] == '}') {
               --depth;
               if (depth == 0) {
                 ++e;
                 break;
               }
             }
           }
           return state.substr(b, e - b);
         }() +
         ",\"morning\":{\"slot\":\"morning\",\"lords_prayer\":\"Our Father in heaven...\","
         "\"note\":\"Read today's chapter, then pray. Mark done to set SoftLand bible_done.\",\"notes\":\"\"},"
         "\"afternoon\":{\"book\":\"Proverbs\",\"chapter\":" +
         std::to_string(prov) + ",\"key\":\"" + aftKey + "\",\"label\":\"Proverbs " +
         std::to_string(prov) + "\",\"slot\":\"afternoon\",\"done\":" + (aftDone ? "true" : "false") +
         ",\"notes\":\"\",\"note\":\"Afternoon Proverbs.\"},"
         "\"evening\":{\"book\":\"Psalms\",\"chapter\":" + std::to_string(psalm) + ",\"key\":\"" +
         eveKey + "\",\"label\":\"Psalms " + std::to_string(psalm) +
         "\",\"slot\":\"evening\",\"done\":" + (eveDone ? "true" : "false") +
         ",\"notes\":\"\",\"note\":\"Evening Psalms + worship.\","
         "\"worship_title\":\"How Great Thou Art\",\"worship_opening\":\"O Lord my God...\","
         "\"hymn_id\":\"how-great-thou-art\"},"
         "\"morning_chapter\":null,\"afternoon_chapter\":null,\"evening_chapter\":null,"
         "\"hymns_catalog\":[],\"gate\":{}}";
}

bool LifeBibleDevotionDone(int userId, const std::string& slot, bool done,
                           const std::wstring& bibleDataDir, const std::wstring& behaviorDir,
                           std::string* outJson) {
  if (slot == "morning") {
    LifeBibleEnsureToday(userId, bibleDataDir);
    std::string day = LocalDateYmd();
    std::string doc;
    LoadDayRow(userId, day, &doc);
    auto plan = LoadPlan(bibleDataDir);
    PlanChapter a = AssignedFromDoc(doc, plan);
    std::string state;
    if (!LifeBibleTick(userId, a.book, a.chapter, done, bibleDataDir, behaviorDir, &state))
      return false;
    if (outJson) *outJson = LifeBibleDevotionTodayJson(userId, bibleDataDir);
    return true;
  }
  LifeBibleEnsureToday(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  if (!LoadDayRow(userId, day, &doc)) return false;
  std::string flag = slot == "afternoon" ? "afternoon_done" : "evening_done";
  std::string needle = std::string("\"") + flag + "\"";
  size_t p = doc.find(needle);
  std::string val = done ? "true" : "false";
  if (p == std::string::npos) {
    // inject into devotion object or top-level
    size_t d = doc.find("\"devotion\"");
    if (d != std::string::npos) {
      size_t brace = doc.find('{', d);
      if (brace != std::string::npos) {
        doc.insert(brace + 1, std::string("\"") + flag + "\":" + val + ",");
      }
    } else {
      doc.insert(doc.size() - 1, std::string(",\"") + flag + "\":" + val);
    }
  } else {
    size_t colon = doc.find(':', p);
    size_t i = colon + 1;
    while (i < doc.size() && (doc[i] == ' ' || doc[i] == '\t')) ++i;
    size_t j = i;
    while (j < doc.size() && isalpha((unsigned char)doc[j])) ++j;
    doc.replace(i, j - i, val);
  }
  SaveDayRow(userId, day, doc);
  if (outJson) *outJson = LifeBibleDevotionTodayJson(userId, bibleDataDir);
  return true;
}

bool LifeBibleDevotionNotes(int userId, const std::string& slot, const std::string& notes,
                            const std::wstring& bibleDataDir, std::string* outJson) {
  LifeBibleEnsureToday(userId, bibleDataDir);
  std::string day = LocalDateYmd();
  std::string doc;
  if (!LoadDayRow(userId, day, &doc)) return false;
  std::string field = slot == "morning"     ? "morning_notes"
                      : slot == "afternoon" ? "afternoon_notes"
                                            : "evening_notes";
  // Store simply at top-level for now
  std::string needle = std::string("\"") + field + "\"";
  size_t p = doc.find(needle);
  std::string esc = EscapeJson(notes.substr(0, 4000));
  if (p == std::string::npos) {
    doc.insert(doc.size() - 1, std::string(",\"") + field + "\":\"" + esc + "\"");
  } else {
    size_t colon = doc.find(':', p);
    size_t q1 = doc.find('"', colon + 1);
    size_t q2 = q1 == std::string::npos ? std::string::npos : doc.find('"', q1 + 1);
    if (q1 != std::string::npos && q2 != std::string::npos) {
      doc.replace(q1, q2 - q1 + 1, std::string("\"") + esc + "\"");
    }
  }
  SaveDayRow(userId, day, doc);
  if (outJson) *outJson = LifeBibleDevotionTodayJson(userId, bibleDataDir);
  return true;
}
