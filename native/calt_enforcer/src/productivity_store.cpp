#include "productivity_store.h"
#include "sqlite3.h"

#include <windows.h>

#include <cctype>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

sqlite3* gDb = nullptr;
std::wstring gDbPath;

std::string Narrow(const std::wstring& w) {
  if (w.empty()) return {};
  int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  std::string s(n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), s.data(), n, nullptr, nullptr);
  return s;
}

std::wstring DirOf(const std::wstring& path) {
  size_t slash = path.find_last_of(L"\\/");
  return (slash == std::wstring::npos) ? L"." : path.substr(0, slash);
}

std::wstring Join(const std::wstring& a, const std::wstring& b) {
  if (a.empty()) return b;
  if (a.back() == L'\\' || a.back() == L'/') return a + b;
  return a + L"\\" + b;
}

std::string ReadFileUtf8(const std::wstring& path) {
  FILE* f = nullptr;
#if defined(_MSC_VER)
  _wfopen_s(&f, path.c_str(), L"rb");
#else
  f = _wfopen(path.c_str(), L"rb");
#endif
  if (!f) return {};
  std::string body;
  char buf[4096];
  while (size_t n = fread(buf, 1, sizeof(buf), f)) body.append(buf, n);
  fclose(f);
  if (!body.empty() && (unsigned char)body[0] == 0xEF && body.size() >= 3 &&
      (unsigned char)body[1] == 0xBB && (unsigned char)body[2] == 0xBF) {
    body.erase(0, 3);
  }
  return body;
}

bool JsonBoolNear(const std::string& body, const char* key, bool* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t' || body[i] == '\r' || body[i] == '\n'))
    ++i;
  if (body.compare(i, 4, "true") == 0) {
    *out = true;
    return true;
  }
  if (body.compare(i, 5, "false") == 0) {
    *out = false;
    return true;
  }
  return false;
}

bool JsonStringNear(const std::string& body, const char* key, std::string* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t' || body[i] == '\r' || body[i] == '\n'))
    ++i;
  if (i < body.size() && body.compare(i, 4, "null") == 0) {
    *out = "";
    return true;
  }
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

bool JsonIntNear(const std::string& body, const char* key, int* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t')) ++i;
  if (i >= body.size() || !(isdigit((unsigned char)body[i]) || body[i] == '-')) return false;
  *out = atoi(body.c_str() + i);
  return true;
}

std::string IsoLocalNow() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u", st.wYear, st.wMonth, st.wDay, st.wHour,
           st.wMinute, st.wSecond);
  return buf;
}

bool ReplaceJsonBool(std::string& doc, const char* key, bool v) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = doc.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = doc.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < doc.size() && (doc[i] == ' ' || doc[i] == '\t')) ++i;
  const char* rep = v ? "true" : "false";
  size_t len = 0;
  if (doc.compare(i, 4, "true") == 0)
    len = 4;
  else if (doc.compare(i, 5, "false") == 0)
    len = 5;
  else
    return false;
  doc.replace(i, len, rep);
  return true;
}

bool ReplaceJsonStringOrNull(std::string& doc, const char* key, const std::string& val) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = doc.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = doc.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < doc.size() && (doc[i] == ' ' || doc[i] == '\t' || doc[i] == '\r' || doc[i] == '\n'))
    ++i;
  size_t end = i;
  if (doc.compare(i, 4, "null") == 0) {
    end = i + 4;
  } else if (doc[i] == '"') {
    end = i + 1;
    while (end < doc.size() && doc[end] != '"') {
      if (doc[end] == '\\' && end + 1 < doc.size()) end += 2;
      else
        ++end;
    }
    if (end < doc.size()) ++end;
  } else
    return false;
  std::string rep = val.empty() ? "null" : ("\"" + val + "\"");
  doc.replace(i, end - i, rep);
  return true;
}

/** Wall-clock prefix of an ISO stamp — Python writes an offset, C++ does not. */
std::string IsoWall(const std::string& iso) {
  return iso.size() >= 19 ? iso.substr(0, 19) : iso;
}

std::string JsonEscape(const std::string& in) {
  std::string out;
  out.reserve(in.size() + 8);
  for (char c : in) {
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if ((unsigned char)c < 0x20)
          out += ' ';
        else
          out += c;
    }
  }
  return out;
}

bool Exec(const char* sql) {
  if (!gDb) return false;
  char* err = nullptr;
  int rc = sqlite3_exec(gDb, sql, nullptr, nullptr, &err);
  if (err) sqlite3_free(err);
  return rc == SQLITE_OK;
}

std::string LocalDateStr() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02u", st.wYear, st.wMonth, st.wDay);
  return buf;
}

/** Monday-start week key, local time. Day passes are a per-week quota. */
std::string WeekStartStr() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  int back = (st.wDayOfWeek == 0) ? 6 : (st.wDayOfWeek - 1);  // wDayOfWeek: 0=Sunday
  FILETIME ft;
  if (!SystemTimeToFileTime(&st, &ft)) return LocalDateStr();
  ULARGE_INTEGER uli;
  uli.LowPart = ft.dwLowDateTime;
  uli.HighPart = ft.dwHighDateTime;
  uli.QuadPart -= (ULONGLONG)back * 24ULL * 3600ULL * 10000000ULL;
  ft.dwLowDateTime = uli.LowPart;
  ft.dwHighDateTime = uli.HighPart;
  SYSTEMTIME out;
  if (!FileTimeToSystemTime(&ft, &out)) return LocalDateStr();
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02u", out.wYear, out.wMonth, out.wDay);
  return buf;
}

/** Strings from a JSON array, keeping only "YYYY-MM-DD" tokens. */
void ParseDateArrayNear(const std::string& body, const char* key,
                        std::vector<std::string>& out) {
  out.clear();
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return;
  size_t lb = body.find('[', p);
  size_t rb = (lb == std::string::npos) ? std::string::npos : body.find(']', lb);
  if (lb == std::string::npos || rb == std::string::npos) return;
  for (size_t i = lb + 1; i < rb;) {
    if (body[i] != '"') {
      ++i;
      continue;
    }
    size_t j = body.find('"', i + 1);
    if (j == std::string::npos || j > rb) break;
    std::string tok = body.substr(i + 1, j - i - 1);
    if (tok.size() == 10 && tok[4] == '-' && tok[7] == '-') out.push_back(tok);
    i = j + 1;
  }
}

/** Single-column COUNT/int query with one optional text bind. */
int ScalarInt(const char* sql, const std::string* bind1, const char* bind2) {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb, sql, -1, &st, nullptr) != SQLITE_OK) return 0;
  int idx = 1;
  if (bind1) sqlite3_bind_text(st, idx++, bind1->c_str(), -1, SQLITE_TRANSIENT);
  if (bind2) sqlite3_bind_text(st, idx++, bind2, -1, SQLITE_STATIC);
  int n = 0;
  if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  sqlite3_finalize(st);
  return n;
}

}  // namespace

void ProductivityRefreshCacheFromDocument(ProductivitySoftland& s) {
  JsonBoolNear(s.document_json, "softland_enabled", &s.softland_enabled);
  JsonStringNear(s.document_json, "free_until", &s.free_until);
  JsonStringNear(s.document_json, "incubation_until", &s.incubation_until);
  JsonBoolNear(s.document_json, "reward_day_active", &s.reward_day_active);
  JsonIntNear(s.document_json, "earned_ledger_seconds", &s.earned_ledger_seconds);
  JsonIntNear(s.document_json, "schema_version", &s.schema_version);
  JsonStringNear(s.document_json, "updated_at", &s.updated_at);
}

bool ProductivityApplyCacheToDocument(ProductivitySoftland& s) {
  if (s.document_json.empty()) return false;
  ReplaceJsonBool(s.document_json, "softland_enabled", s.softland_enabled);
  ReplaceJsonStringOrNull(s.document_json, "free_until", s.free_until);
  ReplaceJsonStringOrNull(s.document_json, "incubation_until", s.incubation_until);
  ReplaceJsonBool(s.document_json, "reward_day_active", s.reward_day_active);
  ReplaceJsonStringOrNull(s.document_json, "updated_at", s.updated_at.empty() ? IsoLocalNow() : s.updated_at);
  // earned_ledger_seconds — simple replace if present
  {
    std::string needle = "\"earned_ledger_seconds\"";
    size_t p = s.document_json.find(needle);
    if (p != std::string::npos) {
      size_t colon = s.document_json.find(':', p + needle.size());
      if (colon != std::string::npos) {
        size_t i = colon + 1;
        while (i < s.document_json.size() &&
               (s.document_json[i] == ' ' || s.document_json[i] == '\t'))
          ++i;
        size_t j = i;
        while (j < s.document_json.size() &&
               (isdigit((unsigned char)s.document_json[j]) || s.document_json[j] == '-'))
          ++j;
        s.document_json.replace(i, j - i, std::to_string(s.earned_ledger_seconds));
      }
    }
  }
  return true;
}

bool ProductivityReplaceJsonValue(std::string& doc, const char* key,
                                  const std::string& rawValueJson) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = doc.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = doc.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < doc.size() && isspace((unsigned char)doc[i])) ++i;
  if (i >= doc.size()) return false;

  size_t end = i;
  if (doc[i] == '{' || doc[i] == '[') {
    char open = doc[i];
    char close = open == '{' ? '}' : ']';
    int depth = 0;
    bool inStr = false;
    for (end = i; end < doc.size(); ++end) {
      char c = doc[end];
      if (inStr) {
        if (c == '\\') {
          ++end;
        } else if (c == '"') {
          inStr = false;
        }
        continue;
      }
      if (c == '"')
        inStr = true;
      else if (c == open)
        ++depth;
      else if (c == close && --depth == 0) {
        ++end;
        break;
      }
    }
    if (depth != 0) return false;
  } else if (doc[i] == '"') {
    end = i + 1;
    while (end < doc.size() && doc[end] != '"') {
      if (doc[end] == '\\' && end + 1 < doc.size())
        end += 2;
      else
        ++end;
    }
    if (end < doc.size()) ++end;
  } else {
    while (end < doc.size() && doc[end] != ',' && doc[end] != '}' && doc[end] != ']') ++end;
    while (end > i && isspace((unsigned char)doc[end - 1])) --end;
  }
  doc.replace(i, end - i, rawValueJson);
  return true;
}

bool ProductivityImportIfStale(const std::wstring& softlandJsonPath) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  std::string rowUpdated;
  if (sqlite3_prepare_v2(gDb, "SELECT updated_at FROM productivity_softland WHERE id=1;", -1, &st,
                         nullptr) != SQLITE_OK) {
    return false;
  }
  bool hasRow = sqlite3_step(st) == SQLITE_ROW;
  if (hasRow) {
    const char* p = reinterpret_cast<const char*>(sqlite3_column_text(st, 0));
    rowUpdated = p ? p : "";
  }
  sqlite3_finalize(st);
  if (!hasRow) return false;

  // A Python writer (reward day, legacy Settings) may have edited the mirror
  // while the gateway was down or in parallel. Newer wall clock wins.
  std::string fileBody = ReadFileUtf8(softlandJsonPath);
  if (fileBody.empty()) return false;
  std::string fileUpdated;
  if (!JsonStringNear(fileBody, "updated_at", &fileUpdated) || fileUpdated.empty()) return false;
  if (IsoWall(fileUpdated) <= IsoWall(rowUpdated)) return false;

  if (sqlite3_prepare_v2(gDb,
                         "UPDATE productivity_softland SET document_json=?, updated_at=? WHERE id=1;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_text(st, 1, fileBody.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, fileUpdated.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityDuePending(const std::string& nowIsoLocal,
                            std::vector<ProductivityPendingRow>& out) {
  out.clear();
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT id, op, payload_json FROM productivity_pending_changes "
                         "WHERE status='pending' AND substr(apply_after,1,19) <= ? "
                         "ORDER BY id ASC;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string wall = IsoWall(nowIsoLocal);
  sqlite3_bind_text(st, 1, wall.c_str(), -1, SQLITE_TRANSIENT);
  while (sqlite3_step(st) == SQLITE_ROW) {
    ProductivityPendingRow row;
    row.id = sqlite3_column_int64(st, 0);
    const char* op = reinterpret_cast<const char*>(sqlite3_column_text(st, 1));
    const char* pl = reinterpret_cast<const char*>(sqlite3_column_text(st, 2));
    row.op = op ? op : "";
    row.payload_json = pl ? pl : "{}";
    out.push_back(row);
  }
  sqlite3_finalize(st);
  return true;
}

bool ProductivityMarkPending(long long id, const char* status) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb, "UPDATE productivity_pending_changes SET status=? WHERE id=?;", -1,
                         &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_text(st, 1, status, -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 2, id);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityInsertPending(const std::string& applyAfterIso, const std::string& op,
                               const std::string& payloadJson) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT INTO productivity_pending_changes (created_at, apply_after, op, "
                         "payload_json, status) VALUES (?, ?, ?, ?, 'pending');",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string now = IsoLocalNow();
  sqlite3_bind_text(st, 1, now.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, applyAfterIso.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, op.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, payloadJson.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityLedgerAdd(const char* kind, int seconds, const std::string& note,
                           const char* source) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT INTO productivity_ledger (ts, kind, seconds, note, source) "
                         "VALUES (?, ?, ?, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string now = IsoLocalNow();
  sqlite3_bind_text(st, 1, now.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, kind, -1, SQLITE_TRANSIENT);
  sqlite3_bind_int(st, 3, seconds);
  sqlite3_bind_text(st, 4, note.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 5, source ? source : "gateway", -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::string ProductivityLedgerRecentJson(int limit) {
  if (!gDb) return "[]";
  if (limit <= 0 || limit > 500) limit = 50;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT ts, kind, seconds, note, source FROM productivity_ledger "
                         "ORDER BY id DESC LIMIT ?;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return "[]";
  }
  sqlite3_bind_int(st, 1, limit);
  std::string out = "[";
  bool first = true;
  while (sqlite3_step(st) == SQLITE_ROW) {
    auto col = [&](int i) -> std::string {
      const char* p = reinterpret_cast<const char*>(sqlite3_column_text(st, i));
      return p ? p : "";
    };
    if (!first) out += ",";
    first = false;
    out += "{\"ts\":\"" + JsonEscape(col(0)) + "\",\"kind\":\"" + JsonEscape(col(1)) +
           "\",\"seconds\":" + std::to_string(sqlite3_column_int(st, 2)) + ",\"note\":\"" +
           JsonEscape(col(3)) + "\",\"source\":\"" + JsonEscape(col(4)) + "\"}";
  }
  sqlite3_finalize(st);
  out += "]";
  return out;
}

std::string ProductivityPendingListJson(int limit) {
  if (!gDb) return "[]";
  if (limit <= 0 || limit > 200) limit = 20;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT id, created_at, apply_after, op, payload_json, status FROM "
                         "productivity_pending_changes WHERE status='pending' ORDER BY id ASC "
                         "LIMIT ?;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return "[]";
  }
  sqlite3_bind_int(st, 1, limit);
  std::string out = "[";
  bool first = true;
  while (sqlite3_step(st) == SQLITE_ROW) {
    auto col = [&](int i) -> std::string {
      const char* p = reinterpret_cast<const char*>(sqlite3_column_text(st, i));
      return p ? p : "";
    };
    if (!first) out += ",";
    first = false;
    out += "{\"id\":" + std::to_string(sqlite3_column_int64(st, 0)) + ",\"created_at\":\"" +
           JsonEscape(col(1)) + "\",\"apply_after\":\"" + JsonEscape(col(2)) + "\",\"op\":\"" +
           JsonEscape(col(3)) + "\",\"payload\":" + (col(4).empty() ? "{}" : col(4)) +
           ",\"status\":\"" + JsonEscape(col(5)) + "\"}";
  }
  sqlite3_finalize(st);
  out += "]";
  return out;
}

std::wstring ProductivityBehaviorDirFromDb(const std::wstring& dbPath) {
  return Join(DirOf(dbPath), L"behavior");
}

bool ProductivityStoreOpen(const std::wstring& dbPath) {
  ProductivityStoreClose();
  gDbPath = dbPath;
  std::string path = Narrow(dbPath);
  if (sqlite3_open_v2(path.c_str(), &gDb, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr) !=
      SQLITE_OK) {
    if (gDb) {
      sqlite3_close(gDb);
      gDb = nullptr;
    }
    return false;
  }
  sqlite3_busy_timeout(gDb, 5000);
  sqlite3_exec(gDb, "PRAGMA journal_mode=WAL;", nullptr, nullptr, nullptr);
  return true;
}

void ProductivityStoreClose() {
  if (gDb) {
    sqlite3_close(gDb);
    gDb = nullptr;
  }
}

bool ProductivityMigrateAndImport(const std::wstring& softlandJsonPath) {
  if (!gDb) return false;
  const char* ddl =
      "CREATE TABLE IF NOT EXISTS productivity_softland ("
      "  id INTEGER PRIMARY KEY CHECK (id = 1),"
      "  document_json TEXT NOT NULL,"
      "  updated_at TEXT NOT NULL"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_ledger ("
      "  id INTEGER PRIMARY KEY,"
      "  ts TEXT NOT NULL,"
      "  kind TEXT NOT NULL,"
      "  seconds INTEGER NOT NULL,"
      "  note TEXT,"
      "  source TEXT"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_pending_changes ("
      "  id INTEGER PRIMARY KEY,"
      "  created_at TEXT NOT NULL,"
      "  apply_after TEXT NOT NULL,"
      "  op TEXT NOT NULL,"
      "  payload_json TEXT NOT NULL,"
      "  status TEXT NOT NULL"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_gateway_meta ("
      "  id INTEGER PRIMARY KEY CHECK (id = 1),"
      "  gateway_seq INTEGER NOT NULL,"
      "  last_publish_at TEXT"
      ");"
      // P5a — unlock accounting owned by the enforcer, not the study webapp.
      "CREATE TABLE IF NOT EXISTS productivity_day_passes ("
      "  local_date TEXT PRIMARY KEY,"
      "  week_start TEXT NOT NULL,"
      "  granted_at TEXT NOT NULL,"
      "  source TEXT NOT NULL DEFAULT 'gateway'"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_reward_credits ("
      "  local_date TEXT NOT NULL,"
      "  kind TEXT NOT NULL,"  // 'qualified' | 'used'
      "  recorded_at TEXT NOT NULL,"
      "  PRIMARY KEY (local_date, kind)"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_reward_meta ("
      "  id INTEGER PRIMARY KEY CHECK (id = 1),"
      "  granted INTEGER NOT NULL DEFAULT 0"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_day_events ("
      "  local_date TEXT NOT NULL,"
      "  event TEXT NOT NULL,"
      "  at TEXT NOT NULL,"
      "  earned_seconds INTEGER NOT NULL DEFAULT 0,"
      "  PRIMARY KEY (local_date, event)"
      ");";
  if (!Exec(ddl)) return false;
  Exec("INSERT OR IGNORE INTO productivity_gateway_meta (id, gateway_seq, last_publish_at) "
       "VALUES (1, 0, NULL);");
  Exec("INSERT OR IGNORE INTO productivity_reward_meta (id, granted) VALUES (1, 0);");

  sqlite3_stmt* st = nullptr;
  bool hasRow = false;
  std::string rowUpdated;
  if (sqlite3_prepare_v2(gDb, "SELECT updated_at FROM productivity_softland WHERE id=1;", -1, &st,
                         nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) {
      hasRow = true;
      const char* p = reinterpret_cast<const char*>(sqlite3_column_text(st, 0));
      rowUpdated = p ? p : "";
    }
    sqlite3_finalize(st);
  }
  if (hasRow) {
    ProductivityImportIfStale(softlandJsonPath);
    return true;
  }
  (void)rowUpdated;

  std::string body = ReadFileUtf8(softlandJsonPath);
  if (body.empty()) {
    body =
        "{\n  \"schema_version\": 1,\n  \"updated_at\": null,\n  \"softland_enabled\": false,\n"
        "  \"site_rules\": {\"allow_extra\": [], \"watch_extra\": [], \"block_extra\": []},\n"
        "  \"schedules\": {\"enabled\": false, \"windows\": []},\n"
        "  \"runtime\": {\"free_until\": null, \"free_after_hm\": null, \"incubation_until\": null,\n"
        "    \"day_pass\": {\"date\": null, \"spent\": false, \"remaining_seconds\": 0},\n"
        "    \"reward_day_active\": false, \"earned_ledger_seconds\": 0},\n"
        "  \"goals\": {\"daily_focus_minutes\": 0, \"goal_met\": false, \"bible_done\": false,\n"
        "    \"plan_confirmed_for_date\": null, \"plan_confirmed\": false},\n"
        "  \"mode_flags\": {}\n}\n";
  }
  std::string now = IsoLocalNow();
  if (sqlite3_prepare_v2(gDb,
                         "INSERT INTO productivity_softland (id, document_json, updated_at) "
                         "VALUES (1, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_text(st, 1, body.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityLoadSoftland(ProductivitySoftland& out) {
  out = ProductivitySoftland{};
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT document_json, updated_at FROM productivity_softland WHERE id=1;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  bool ok = false;
  if (sqlite3_step(st) == SQLITE_ROW) {
    const char* doc = reinterpret_cast<const char*>(sqlite3_column_text(st, 0));
    const char* upd = reinterpret_cast<const char*>(sqlite3_column_text(st, 1));
    out.document_json = doc ? doc : "";
    out.updated_at = upd ? upd : "";
    ProductivityRefreshCacheFromDocument(out);
    ok = true;
  }
  sqlite3_finalize(st);
  return ok;
}

bool ProductivitySaveSoftland(const ProductivitySoftland& in) {
  if (!gDb || in.document_json.empty()) return false;
  ProductivitySoftland tmp = in;
  if (tmp.updated_at.empty()) tmp.updated_at = IsoLocalNow();
  ProductivityApplyCacheToDocument(tmp);
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "UPDATE productivity_softland SET document_json=?, updated_at=? WHERE id=1;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_text(st, 1, tmp.document_json.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, tmp.updated_at.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

unsigned ProductivityBumpSeq() {
  if (!gDb) return 0;
  Exec("UPDATE productivity_gateway_meta SET gateway_seq = gateway_seq + 1 WHERE id=1;");
  ProductivityGatewayMeta m;
  if (!ProductivityLoadMeta(m)) return 0;
  return m.gateway_seq;
}

bool ProductivityLoadMeta(ProductivityGatewayMeta& out) {
  out = ProductivityGatewayMeta{};
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT gateway_seq, last_publish_at FROM productivity_gateway_meta WHERE "
                         "id=1;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  bool ok = false;
  if (sqlite3_step(st) == SQLITE_ROW) {
    out.gateway_seq = (unsigned)sqlite3_column_int(st, 0);
    const char* p = reinterpret_cast<const char*>(sqlite3_column_text(st, 1));
    out.last_publish_at = p ? p : "";
    ok = true;
  }
  sqlite3_finalize(st);
  return ok;
}

// ---------------------------------------------------------------------------
// P5a — day passes, reward credits, per-day events
// ---------------------------------------------------------------------------

std::string ProductivityLocalDate() { return LocalDateStr(); }
std::string ProductivityWeekStart() { return WeekStartStr(); }

int ProductivityPassesUsedThisWeek() {
  std::string wk = WeekStartStr();
  return ScalarInt("SELECT COUNT(*) FROM productivity_day_passes WHERE week_start = ?;", &wk,
                   nullptr);
}

bool ProductivityPassGrantedToday() {
  std::string d = LocalDateStr();
  return ScalarInt("SELECT COUNT(*) FROM productivity_day_passes WHERE local_date = ?;", &d,
                   nullptr) > 0;
}

bool ProductivityInsertPass(const std::string& localDate, const std::string& weekStart) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_day_passes "
                         "(local_date, week_start, granted_at, source) VALUES (?, ?, ?, 'gateway');",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string now = IsoLocalNow();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, weekStart.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

int ProductivityRewardCount(const char* kind) {
  return ScalarInt("SELECT COUNT(*) FROM productivity_reward_credits WHERE kind = ?;", nullptr,
                   kind);
}

int ProductivityRewardGranted() {
  return ScalarInt("SELECT granted FROM productivity_reward_meta WHERE id = 1;", nullptr, nullptr);
}

bool ProductivityRewardSetGranted(int granted) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb, "UPDATE productivity_reward_meta SET granted = ? WHERE id = 1;", -1,
                         &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_int(st, 1, granted < 0 ? 0 : granted);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityRewardMark(const char* kind, const std::string& localDate) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_reward_credits "
                         "(local_date, kind, recorded_at) VALUES (?, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string now = IsoLocalNow();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, kind, -1, SQLITE_STATIC);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityDayEventSeconds(const std::string& localDate, const std::string& event,
                                 int* outSeconds) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT earned_seconds FROM productivity_day_events "
                         "WHERE local_date = ? AND event = ?;",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, event.c_str(), -1, SQLITE_TRANSIENT);
  bool found = false;
  if (sqlite3_step(st) == SQLITE_ROW) {
    found = true;
    if (outSeconds) *outSeconds = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return found;
}

int ProductivityDayEarnedSecondsToday() {
  std::string d = LocalDateStr();
  return ScalarInt("SELECT COALESCE(SUM(earned_seconds), 0) FROM productivity_day_events "
                   "WHERE local_date = ?;",
                   &d, nullptr);
}

bool ProductivityInsertDayEvent(const std::string& localDate, const std::string& event,
                                int earnedSeconds) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_day_events "
                         "(local_date, event, at, earned_seconds) VALUES (?, ?, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK) {
    return false;
  }
  std::string now = IsoLocalNow();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, event.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int(st, 4, earnedSeconds);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

int ProductivityIncubationStartsSinceIso(const std::string& sinceIso) {
  return ScalarInt("SELECT COUNT(*) FROM productivity_ledger "
                   "WHERE kind = 'incubation' AND ts >= ?;",
                   &sinceIso, nullptr);
}

void ProductivityImportLegacyUnlockHistory(const std::wstring& dataDir) {
  if (!gDb) return;
  // Import only into empty tables — re-running must not resurrect rows the
  // owner deleted on purpose, and must not double-count history.
  const bool haveRewards =
      ProductivityRewardCount("qualified") > 0 || ProductivityRewardCount("used") > 0;
  const bool havePasses = ScalarInt("SELECT COUNT(*) FROM productivity_day_passes;", nullptr,
                                    nullptr) > 0;
  if (haveRewards && havePasses) return;

  const std::wstring bibleDir = dataDir + L"\\bible";

  if (!haveRewards) {
    WIN32_FIND_DATAW fd{};
    HANDLE h = FindFirstFileW((bibleDir + L"\\reward_days_*.json").c_str(), &fd);
    if (h != INVALID_HANDLE_VALUE) {
      do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        std::string body = ReadFileUtf8(bibleDir + L"\\" + fd.cFileName);
        if (body.empty()) continue;
        std::vector<std::string> dates;
        ParseDateArrayNear(body, "qualified_dates", dates);
        for (const auto& d : dates) ProductivityRewardMark("qualified", d);
        ParseDateArrayNear(body, "used_dates", dates);
        for (const auto& d : dates) ProductivityRewardMark("used", d);
        int granted = 0;
        if (JsonIntNear(body, "granted", &granted) && granted > 0)
          ProductivityRewardSetGranted(ProductivityRewardGranted() + granted);
      } while (FindNextFileW(h, &fd));
      FindClose(h);
    }
  }

  if (!havePasses) {
    WIN32_FIND_DATAW fd{};
    HANDLE h = FindFirstFileW((bibleDir + L"\\day_passes_*.json").c_str(), &fd);
    if (h != INVALID_HANDLE_VALUE) {
      do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        std::string body = ReadFileUtf8(bibleDir + L"\\" + fd.cFileName);
        if (body.empty()) continue;
        std::string week;
        JsonStringNear(body, "week", &week);
        std::vector<std::string> dates;
        ParseDateArrayNear(body, "dates", dates);
        for (const auto& d : dates)
          ProductivityInsertPass(d, week.empty() ? d : week);
      } while (FindNextFileW(h, &fd));
      FindClose(h);
    }
  }
}
