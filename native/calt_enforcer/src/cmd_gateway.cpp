#include "cmd_gateway.h"
#include "policy_db.h"
#include "productivity_store.h"
#include "softland_publish.h"

#include <windows.h>

#include <cctype>
#include <cstdio>
#include <string>
#include <vector>

namespace {

HANDLE gPipe = INVALID_HANDLE_VALUE;
const wchar_t* kPipeName = L"\\\\.\\pipe\\calt_enforcer_cmd";

std::string IsoLocalNow() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u", st.wYear, st.wMonth, st.wDay, st.wHour,
           st.wMinute, st.wSecond);
  return buf;
}

bool JsonGetString(const std::string& body, const char* key, std::string* out) {
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

bool JsonGetBool(const std::string& body, const char* key, bool* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t')) ++i;
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

bool JsonGetInt(const std::string& body, const char* key, int* out) {
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

std::string ExtractPayload(const std::string& body) {
  std::string needle = "\"payload\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return "{}";
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return "{}";
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t')) ++i;
  if (i >= body.size() || body[i] != '{') return "{}";
  int depth = 0;
  size_t start = i;
  for (; i < body.size(); ++i) {
    if (body[i] == '{')
      ++depth;
    else if (body[i] == '}') {
      --depth;
      if (depth == 0) return body.substr(start, i - start + 1);
    }
  }
  return "{}";
}

/** Raw JSON text of payload[key] — objects, arrays and scalars alike. */
bool JsonGetRaw(const std::string& body, const char* key, std::string* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && isspace((unsigned char)body[i])) ++i;
  if (i >= body.size()) return false;
  size_t end = i;
  if (body[i] == '{' || body[i] == '[') {
    char open = body[i];
    char close = open == '{' ? '}' : ']';
    int depth = 0;
    bool inStr = false;
    for (end = i; end < body.size(); ++end) {
      char c = body[end];
      if (inStr) {
        if (c == '\\')
          ++end;
        else if (c == '"')
          inStr = false;
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
  } else if (body[i] == '"') {
    end = i + 1;
    while (end < body.size() && body[end] != '"') {
      if (body[end] == '\\' && end + 1 < body.size())
        end += 2;
      else
        ++end;
    }
    if (end < body.size()) ++end;
  } else {
    while (end < body.size() && body[end] != ',' && body[end] != '}' && body[end] != ']') ++end;
    while (end > i && isspace((unsigned char)body[end - 1])) --end;
  }
  *out = body.substr(i, end - i);
  return !out->empty();
}

/** Rebuild a host array from payload so only sanitized strings reach the doc. */
bool SanitizedHostArray(const std::string& raw, std::string* out) {
  if (raw.empty() || raw[0] != '[') return false;
  std::string arr = "[";
  size_t i = 0;
  bool first = true;
  while (i < raw.size()) {
    if (raw[i] == '"') {
      std::string tok;
      size_t j = i + 1;
      while (j < raw.size() && raw[j] != '"') {
        if (raw[j] == '\\' && j + 1 < raw.size()) {
          tok.push_back(raw[j + 1]);
          j += 2;
          continue;
        }
        tok.push_back(raw[j++]);
      }
      i = (j < raw.size()) ? j + 1 : j;
      std::string host;
      for (char c : tok) {
        unsigned char u = (unsigned char)c;
        if (isalnum(u) || c == '.' || c == '-' || c == '_') host.push_back((char)tolower(u));
      }
      if (host.size() < 3 || host.find('.') == std::string::npos) continue;
      if (!first) arr += ",";
      first = false;
      arr += "\"" + host + "\"";
      continue;
    }
    ++i;
  }
  arr += "]";
  *out = arr;
  return true;
}

/** Reject raw JSON we would not want spliced into the policy document. */
bool RawJsonAcceptable(const std::string& raw, char expectOpen, size_t maxLen) {
  if (raw.empty() || raw[0] != expectOpen || raw.size() > maxLen) return false;
  for (char c : raw) {
    if ((unsigned char)c < 0x20) return false;
  }
  return true;
}

/** Parse YYYY-MM-DDTHH:MM:SS (any trailing offset ignored) as local time. */
bool ParseIsoLocal(const std::string& iso, SYSTEMTIME* out) {
  if (iso.size() < 19) return false;
  unsigned y = 0, mo = 0, d = 0, h = 0, mi = 0, se = 0;
  if (sscanf(iso.c_str(), "%4u-%2u-%2uT%2u:%2u:%2u", &y, &mo, &d, &h, &mi, &se) != 6) return false;
  ZeroMemory(out, sizeof(*out));
  out->wYear = (WORD)y;
  out->wMonth = (WORD)mo;
  out->wDay = (WORD)d;
  out->wHour = (WORD)h;
  out->wMinute = (WORD)mi;
  out->wSecond = (WORD)se;
  return true;
}

std::string AddMinutesLocalIso(int minutes) {
  SYSTEMTIME st;
  GetLocalTime(&st);
  FILETIME ft;
  SystemTimeToFileTime(&st, &ft);
  ULARGE_INTEGER uli;
  uli.LowPart = ft.dwLowDateTime;
  uli.HighPart = ft.dwHighDateTime;
  uli.QuadPart += (ULONGLONG)minutes * 60ULL * 10000000ULL;
  ft.dwLowDateTime = uli.LowPart;
  ft.dwHighDateTime = uli.HighPart;
  SYSTEMTIME outSt;
  FileTimeToSystemTime(&ft, &outSt);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u", outSt.wYear, outSt.wMonth, outSt.wDay,
           outSt.wHour, outSt.wMinute, outSt.wSecond);
  return buf;
}

std::string EndOfLocalDayIso() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT23:59:59", st.wYear, st.wMonth, st.wDay);
  return buf;
}

/**
 * Stack a spend on top of a free window that is still running — otherwise
 * spending 10m during a reward day would cut the day short and burn the ledger.
 */
std::string ExtendFreeWindowIso(const std::string& current, int minutes) {
  SYSTEMTIME base;
  if (!ParseIsoLocal(current, &base)) return AddMinutesLocalIso(minutes);
  FILETIME baseFt, nowFt;
  SYSTEMTIME nowSt;
  GetLocalTime(&nowSt);
  if (!SystemTimeToFileTime(&base, &baseFt) || !SystemTimeToFileTime(&nowSt, &nowFt)) {
    return AddMinutesLocalIso(minutes);
  }
  if (CompareFileTime(&baseFt, &nowFt) <= 0) return AddMinutesLocalIso(minutes);

  ULARGE_INTEGER uli;
  uli.LowPart = baseFt.dwLowDateTime;
  uli.HighPart = baseFt.dwHighDateTime;
  uli.QuadPart += (ULONGLONG)minutes * 60ULL * 10000000ULL;
  baseFt.dwLowDateTime = uli.LowPart;
  baseFt.dwHighDateTime = uli.HighPart;
  SYSTEMTIME outSt;
  FileTimeToSystemTime(&baseFt, &outSt);
  char buf[40];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u", outSt.wYear, outSt.wMonth, outSt.wDay,
           outSt.wHour, outSt.wMinute, outSt.wSecond);
  return buf;
}

std::string SaveAndPublish(ProductivitySoftland& s, const std::wstring& behaviorDir) {
  s.updated_at = IsoLocalNow();
  ProductivityApplyCacheToDocument(s);
  if (!ProductivitySaveSoftland(s)) return "store_save_failed";
  ProductivityBumpSeq();
  PublishSoftlandMirror(behaviorDir, s);
  return "";
}

std::string HandleOp(const std::string& op, const std::string& payload,
                     const std::wstring& behaviorDir, std::string* extraOut) {
  // A Python writer may have touched the mirror since the last tick; import
  // before read-modify-write so its change is not clobbered by this command.
  ProductivityImportIfStale(behaviorDir + L"\\softland_policy.json");

  if (op == "status.snapshot" || op.empty()) return "";

  ProductivitySoftland s;
  if (!ProductivityLoadSoftland(s)) return "store_load_failed";

  if (op == "softland.set_enabled") {
    bool en = false;
    if (!JsonGetBool(payload, "enabled", &en)) return "bad_payload";
    s.softland_enabled = en;
    s.updated_at = IsoLocalNow();
    ProductivityApplyCacheToDocument(s);
    if (!ProductivitySaveSoftland(s)) return "store_save_failed";
    ProductivityBumpSeq();
    PublishSoftlandMirror(behaviorDir, s);
    return "";
  }
  if (op == "softland.set_incubation") {
    std::string until;
    int minutes = 0;
    if (JsonGetString(payload, "until_iso", &until) && !until.empty()) {
      s.incubation_until = until;
    } else if (JsonGetInt(payload, "minutes", &minutes) && minutes > 0) {
      s.incubation_until = AddMinutesLocalIso(minutes);
    } else {
      return "bad_payload";
    }
    s.updated_at = IsoLocalNow();
    ProductivityApplyCacheToDocument(s);
    if (!ProductivitySaveSoftland(s)) return "store_save_failed";
    ProductivityBumpSeq();
    PublishSoftlandMirror(behaviorDir, s);
    return "";
  }
  if (op == "softland.clear_incubation") {
    s.incubation_until.clear();
    s.updated_at = IsoLocalNow();
    ProductivityApplyCacheToDocument(s);
    if (!ProductivitySaveSoftland(s)) return "store_save_failed";
    ProductivityBumpSeq();
    PublishSoftlandMirror(behaviorDir, s);
    return "";
  }
  if (op == "softland.spend_free") {
    int minutes = 0;
    if (!JsonGetInt(payload, "minutes", &minutes) || minutes <= 0) return "bad_payload";
    int need = minutes * 60;
    if (s.earned_ledger_seconds < need) return "insufficient_ledger";
    s.earned_ledger_seconds -= need;
    s.free_until = ExtendFreeWindowIso(s.free_until, minutes);
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    ProductivityLedgerAdd("spend", need, "free window " + std::to_string(minutes) + "m", "gateway");
    return "";
  }
  if (op == "softland.patch_site_rules") {
    std::string section;
    if (!JsonGetRaw(s.document_json, "site_rules", &section)) return "policy_key_missing";
    bool any = false;
    for (const char* key : {"allow_extra", "watch_extra", "block_extra"}) {
      std::string raw;
      if (!JsonGetRaw(payload, key, &raw)) continue;
      std::string clean;
      if (!SanitizedHostArray(raw, &clean)) return "bad_payload";
      if (!ProductivityReplaceJsonValue(section, key, clean)) return "policy_key_missing";
      any = true;
    }
    if (!any) return "bad_payload";
    if (!ProductivityReplaceJsonValue(s.document_json, "site_rules", section))
      return "policy_key_missing";
    return SaveAndPublish(s, behaviorDir);
  }
  if (op == "softland.patch_schedules") {
    // Patch inside the schedules object so generic keys ("enabled") can never
    // hit a same-named key elsewhere in the document.
    std::string section;
    if (!JsonGetRaw(s.document_json, "schedules", &section)) return "policy_key_missing";
    bool any = false;
    bool enabled = false;
    if (JsonGetBool(payload, "enabled", &enabled)) {
      if (!ProductivityReplaceJsonValue(section, "enabled", enabled ? "true" : "false"))
        return "policy_key_missing";
      any = true;
    }
    std::string windows;
    if (JsonGetRaw(payload, "windows", &windows)) {
      if (!RawJsonAcceptable(windows, '[', 64 * 1024)) return "bad_payload";
      if (!ProductivityReplaceJsonValue(section, "windows", windows)) return "policy_key_missing";
      any = true;
    }
    if (!any) return "bad_payload";
    if (!ProductivityReplaceJsonValue(s.document_json, "schedules", section))
      return "policy_key_missing";
    return SaveAndPublish(s, behaviorDir);
  }
  if (op == "softland.patch_mode_flags" || op == "softland.patch_goals") {
    const char* key = op == "softland.patch_mode_flags" ? "mode_flags" : "goals";
    std::string raw;
    if (!JsonGetRaw(payload, key, &raw)) return "bad_payload";
    if (!RawJsonAcceptable(raw, '{', 16 * 1024)) return "bad_payload";
    if (!ProductivityReplaceJsonValue(s.document_json, key, raw)) return "policy_key_missing";
    return SaveAndPublish(s, behaviorDir);
  }
  if (op == "softland.set_reward_day") {
    bool active = false;
    if (!JsonGetBool(payload, "active", &active)) return "bad_payload";
    s.reward_day_active = active;
    std::string until;
    if (active) {
      if (JsonGetString(payload, "free_until", &until) && !until.empty())
        s.free_until = until;
      else
        s.free_until = EndOfLocalDayIso();
    } else {
      s.free_until.clear();
    }
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    ProductivityLedgerAdd("reward_day", 0, active ? "reward day on" : "reward day off", "gateway");
    return "";
  }
  if (op == "softland.set_day_pass") {
    std::string date;
    bool spent = false;
    int remaining = 0;
    JsonGetString(payload, "date", &date);
    JsonGetBool(payload, "spent", &spent);
    JsonGetInt(payload, "remaining_seconds", &remaining);
    if (remaining < 0) remaining = 0;
    std::string obj = std::string("{\"date\": ") + (date.empty() ? "null" : "\"" + date + "\"") +
                      ", \"spent\": " + (spent ? "true" : "false") +
                      ", \"remaining_seconds\": " + std::to_string(remaining) + "}";
    if (!ProductivityReplaceJsonValue(s.document_json, "day_pass", obj)) return "policy_key_missing";
    return SaveAndPublish(s, behaviorDir);
  }
  if (op == "ledger.add") {
    int seconds = 0;
    std::string kind, note;
    if (!JsonGetInt(payload, "seconds", &seconds) || seconds == 0) return "bad_payload";
    if (!JsonGetString(payload, "kind", &kind) || kind.empty()) kind = "adjust";
    if (kind != "earn" && kind != "spend" && kind != "adjust") return "bad_payload";
    JsonGetString(payload, "note", &note);
    long long balance = (long long)s.earned_ledger_seconds + (kind == "spend" ? -seconds : seconds);
    if (balance < 0) balance = 0;
    s.earned_ledger_seconds = (int)balance;
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    ProductivityLedgerAdd(kind.c_str(), seconds, note, "gateway");
    return "";
  }
  if (op == "ledger.snapshot") {
    int limit = 0;
    if (!JsonGetInt(payload, "limit", &limit) || limit <= 0) limit = 50;
    if (extraOut)
      *extraOut = ",\"ledger\":" + ProductivityLedgerRecentJson(limit) +
                  ",\"balance_seconds\":" + std::to_string(s.earned_ledger_seconds);
    return "";
  }
  if (op == "pending.add") {
    std::string innerOp, innerPayload, applyAfter;
    int delay = 0;
    if (!JsonGetString(payload, "op", &innerOp) || innerOp.empty()) return "bad_payload";
    if (!JsonGetRaw(payload, "payload", &innerPayload)) innerPayload = "{}";
    if (!RawJsonAcceptable(innerPayload, '{', 64 * 1024)) return "bad_payload";
    if (JsonGetString(payload, "apply_after_iso", &applyAfter) && !applyAfter.empty()) {
      // caller-supplied stamp
    } else if (JsonGetInt(payload, "delay_minutes", &delay) && delay > 0) {
      applyAfter = AddMinutesLocalIso(delay);
    } else {
      return "bad_payload";
    }
    if (!ProductivityInsertPending(applyAfter, innerOp, innerPayload)) return "pending_insert_failed";
    if (extraOut) *extraOut = ",\"apply_after\":\"" + applyAfter + "\"";
    return "";
  }
  if (op == "pending.list") {
    if (extraOut) *extraOut = ",\"pending\":" + ProductivityPendingListJson(20);
    return "";
  }
  if (op == "pending.cancel") {
    int id = 0;
    if (!JsonGetInt(payload, "id", &id) || id <= 0) return "bad_payload";
    if (!ProductivityMarkPending(id, "cancelled")) return "pending_update_failed";
    if (extraOut) *extraOut = ",\"pending\":" + ProductivityPendingListJson(20);
    return "";
  }
  if (op == "arm.set") {
    EnforcerSnapshot cur;
    std::string loadErr;
    std::wstring polPath = behaviorDir + L"\\enforcer_policy.json";
    // Load existing via LoadEnforcerSnapshot needs dbPath — synthesize from behaviorDir parent
    std::wstring dataDir = behaviorDir;
    size_t slash = dataDir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) dataDir = dataDir.substr(0, slash);
    std::wstring dbPath = dataDir + L"\\vocab_app.db";
    LoadEnforcerSnapshot(dbPath, cur, loadErr);

    bool armed = cur.armed;
    bool locked = cur.locked;
    bool incubation = cur.incubation;
    bool anti = cur.anti_tamper;
    bool protect = false;
    {
      bool hb = false;
      if (JsonGetBool(payload, "hard_block_armed", &hb))
        armed = hb;
      else
        JsonGetBool(payload, "armed", &armed);
    }
    if (!JsonGetBool(payload, "gate_locked", &locked)) locked = armed;
    JsonGetBool(payload, "incubation_active", &incubation);
    JsonGetBool(payload, "anti_tamper", &anti);
    JsonGetBool(payload, "protect_uninstall", &protect);

    std::string mode, pwd, phrase, provided;
    if (JsonGetString(payload, "lock_mode", &mode) && !mode.empty())
      cur.lock_mode = mode;
    else if (cur.lock_mode.empty())
      cur.lock_mode = "none";
    JsonGetString(payload, "unlock_password", &pwd);
    JsonGetString(payload, "unlock_phrase", &phrase);
    JsonGetString(payload, "provided_unlock", &provided);
    int lockUntil = 0;
    if (JsonGetInt(payload, "lock_until_unix", &lockUntil)) cur.lock_until_unix = lockUntil;

    if (!armed && (cur.lock_mode == "password" || cur.lock_mode == "phrase")) {
      const std::string& expect =
          cur.lock_mode == "password" ? cur.unlock_password : cur.unlock_phrase;
      if (!expect.empty() && provided != expect) return "unlock_failed";
    }

    // exes array
    size_t exesKey = payload.find("\"exes\"");
    if (exesKey != std::string::npos) {
      size_t lb = payload.find('[', exesKey);
      size_t rb = payload.find(']', lb == std::string::npos ? 0 : lb);
      if (lb != std::string::npos && rb != std::string::npos && rb > lb) {
        cur.exes.clear();
        std::string arr = payload.substr(lb, rb - lb + 1);
        size_t i = 0;
        while (i < arr.size()) {
          if (arr[i] == '"') {
            size_t j = i + 1;
            std::string tok;
            while (j < arr.size() && arr[j] != '"') {
              if (arr[j] == '\\' && j + 1 < arr.size()) {
                tok.push_back(arr[j + 1]);
                j += 2;
                continue;
              }
              tok.push_back(arr[j++]);
            }
            if (!tok.empty()) {
              for (auto& c : tok) c = (char)tolower((unsigned char)c);
              std::wstring w(tok.begin(), tok.end());
              cur.exes.push_back(w);
            }
            i = (j < arr.size()) ? j + 1 : j;
            continue;
          }
          ++i;
        }
      }
    }

    if (!pwd.empty()) cur.unlock_password = pwd;
    if (!phrase.empty()) cur.unlock_phrase = phrase;
    cur.armed = armed;
    cur.locked = locked;
    cur.incubation = incubation;
    cur.anti_tamper = anti;
    if (cur.lock_mode.empty()) cur.lock_mode = "none";

    if (!WriteEnforcerPolicyJson(polPath, cur, anti, protect)) return "arm_write_failed";
    ProductivityBumpSeq();
    return "";
  }
  return "unknown_op";
}

void EnsurePipe() {
  if (gPipe != INVALID_HANDLE_VALUE) return;
  gPipe = CreateNamedPipeW(kPipeName, PIPE_ACCESS_DUPLEX,
                           PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_NOWAIT, 1, 64 * 1024,
                           64 * 1024, 0, nullptr);
}

/**
 * Recycle the single pipe instance and start listening again immediately —
 * without this a client connecting between two polls sees a broken pipe.
 */
void ResetPipe() {
  if (gPipe != INVALID_HANDLE_VALUE) {
    DisconnectNamedPipe(gPipe);
    CloseHandle(gPipe);
    gPipe = INVALID_HANDLE_VALUE;
  }
  EnsurePipe();
  if (gPipe != INVALID_HANDLE_VALUE) ConnectNamedPipe(gPipe, nullptr);
}

}  // namespace

std::string GatewayApplyOp(const std::string& op, const std::string& payloadJson,
                           const std::wstring& behaviorDir) {
  return HandleOp(op, payloadJson, behaviorDir, nullptr);
}

void CmdGatewayInit() { EnsurePipe(); }

void CmdGatewayShutdown() {
  if (gPipe != INVALID_HANDLE_VALUE) {
    CloseHandle(gPipe);
    gPipe = INVALID_HANDLE_VALUE;
  }
}

void CmdGatewayPoll(const std::wstring& behaviorDir) {
  EnsurePipe();
  if (gPipe == INVALID_HANDLE_VALUE) return;

  BOOL connected = ConnectNamedPipe(gPipe, nullptr) ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);
  if (!connected) {
    DWORD err = GetLastError();
    if (err != ERROR_PIPE_CONNECTED) return;
  }

  char buf[64 * 1024];
  DWORD read = 0;
  if (!ReadFile(gPipe, buf, sizeof(buf) - 1, &read, nullptr) || read == 0) {
    if (GetLastError() != ERROR_NO_DATA) ResetPipe();
    return;
  }
  buf[read] = 0;
  std::string req(buf, read);
  std::string op, id;
  JsonGetString(req, "op", &op);
  JsonGetString(req, "id", &id);
  std::string payload = ExtractPayload(req);
  std::string extra;
  std::string err = HandleOp(op, payload, behaviorDir, &extra);

  ProductivitySoftland s;
  ProductivityLoadSoftland(s);
  ProductivityGatewayMeta meta;
  ProductivityLoadMeta(meta);

  std::string freeJs = s.free_until.empty() ? "null" : ("\"" + s.free_until + "\"");
  std::string incJs = s.incubation_until.empty() ? "null" : ("\"" + s.incubation_until + "\"");
  std::string out;
  if (err.empty()) {
    out = std::string("{\"ok\":true,\"id\":\"") + id + "\",\"gateway_seq\":" +
          std::to_string(meta.gateway_seq) + ",\"as_of\":\"" + IsoLocalNow() +
          "\",\"softland_enabled\":" + (s.softland_enabled ? "true" : "false") +
          ",\"free_until\":" + freeJs + ",\"incubation_until\":" + incJs +
          ",\"reward_day_active\":" + (s.reward_day_active ? "true" : "false") +
          ",\"earned_ledger_seconds\":" + std::to_string(s.earned_ledger_seconds) + extra + "}";
  } else {
    out = std::string("{\"ok\":false,\"id\":\"") + id + "\",\"error\":\"" + err + "\"}";
  }

  DWORD written = 0;
  WriteFile(gPipe, out.data(), (DWORD)out.size(), &written, nullptr);
  FlushFileBuffers(gPipe);
  ResetPipe();
}
