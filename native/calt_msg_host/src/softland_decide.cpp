/**
 * SoftLand get_mode — C++ Productivity decide (Prod P3).
 * Reads data/behavior/softland_policy.json. Never arms OS kills. No Python.
 */

#include "softland_decide.h"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string Narrow(const std::wstring& w) {
  if (w.empty()) return {};
  int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  std::string s(n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), s.data(), n, nullptr, nullptr);
  return s;
}

std::string ToLower(std::string s) {
  for (auto& c : s) c = (char)std::tolower((unsigned char)c);
  return s;
}

bool JsonBoolNear(const std::string& body, const char* key, bool* out) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return false;
  size_t colon = body.find(':', p + needle.size());
  if (colon == std::string::npos) return false;
  size_t i = colon + 1;
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t' || body[i] == '\r' || body[i] == '\n')) ++i;
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
  while (i < body.size() && (body[i] == ' ' || body[i] == '\t' || body[i] == '\r' || body[i] == '\n')) ++i;
  if (i < body.size() && body[i] == 'n') {
    *out = "";
    return true;  // null
  }
  if (i >= body.size() || body[i] != '"') return false;
  ++i;
  std::string tok;
  while (i < body.size() && body[i] != '"') {
    if (body[i] == '\\' && i + 1 < body.size()) {
      tok.push_back(body[i + 1]);
      i += 2;
      continue;
    }
    tok.push_back(body[i++]);
  }
  *out = tok;
  return true;
}

void ParseStringArrayNear(const std::string& body, const char* key, std::vector<std::string>& out) {
  out.clear();
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return;
  size_t lb = body.find('[', p);
  if (lb == std::string::npos) return;
  size_t rb = body.find(']', lb);
  if (rb == std::string::npos || rb <= lb) return;
  std::string arr = body.substr(lb, rb - lb + 1);
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
      if (!tok.empty()) out.push_back(ToLower(tok));
      i = (j < arr.size()) ? j + 1 : j;
      continue;
    }
    ++i;
  }
}

bool FileExistsW(const std::wstring& path) {
  DWORD a = GetFileAttributesW(path.c_str());
  return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

std::wstring JoinPath(const std::wstring& a, const std::wstring& b) {
  if (a.empty()) return b;
  if (a.back() == L'\\' || a.back() == L'/') return a + b;
  return a + L"\\" + b;
}

std::wstring ParentDir(const std::wstring& path) {
  size_t slash = path.find_last_of(L"\\/");
  if (slash == std::wstring::npos) return L".";
  return path.substr(0, slash);
}

std::string ReadFileUtf8(const std::wstring& path) {
  std::ifstream in(Narrow(path), std::ios::binary);
  if (!in) return {};
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::string JsonEscape(const std::string& s) {
  std::string o;
  o.reserve(s.size() + 8);
  for (char c : s) {
    if (c == '"' || c == '\\') {
      o.push_back('\\');
      o.push_back(c);
    } else if (c == '\n') {
      o += "\\n";
    } else {
      o.push_back(c);
    }
  }
  return o;
}

std::string HostFromUrl(const std::string& url) {
  std::string u = ToLower(url);
  size_t scheme = u.find("://");
  size_t start = (scheme == std::string::npos) ? 0 : scheme + 3;
  size_t end = u.find_first_of("/?#", start);
  std::string host = (end == std::string::npos) ? u.substr(start) : u.substr(start, end - start);
  size_t colon = host.find(':');
  if (colon != std::string::npos) host = host.substr(0, colon);
  if (host.rfind("www.", 0) == 0) host = host.substr(4);
  return host;
}

bool HostMatches(const std::string& host, const std::string& domain) {
  if (host.empty() || domain.empty()) return false;
  if (host == domain) return true;
  if (host.size() > domain.size() && host.compare(host.size() - domain.size() - 1, domain.size() + 1, "." + domain) == 0)
    return true;
  return false;
}

bool ListMatch(const std::string& host, const std::vector<std::string>& domains) {
  for (const auto& d : domains) {
    if (HostMatches(host, d)) return true;
  }
  return false;
}

const std::vector<std::string>& BuiltinWatch() {
  static const std::vector<std::string> k = {
      "youtube.com", "youtu.be", "netflix.com", "primevideo.com", "hotstar.com",
      "disneyplus.com", "hulu.com", "twitch.tv", "reddit.com", "twitter.com",
      "x.com", "instagram.com", "facebook.com", "tiktok.com", "discord.com",
  };
  return k;
}

const std::vector<std::string>& BuiltinPornSuffix() {
  static const std::vector<std::string> k = {".xxx", ".porn", ".sex"};
  return k;
}

bool LooksPorn(const std::string& host) {
  for (const auto& s : BuiltinPornSuffix()) {
    if (host.size() >= s.size() && host.compare(host.size() - s.size(), s.size(), s) == 0) return true;
  }
  if (host.find("porn") != std::string::npos) return true;
  if (host.find("xvideos") != std::string::npos) return true;
  if (host.find("pornhub") != std::string::npos) return true;
  return false;
}

struct LocalNow {
  int weekday = 0;  // 0=Mon .. 6=Sun
  int minutes = 0;
  std::time_t unix = 0;
};

LocalNow LocalClock() {
  LocalNow n;
  n.unix = std::time(nullptr);
  std::tm local{};
  localtime_s(&local, &n.unix);
  // tm_wday: 0=Sun → convert to Mon=0
  int w = local.tm_wday;
  n.weekday = (w == 0) ? 6 : (w - 1);
  n.minutes = local.tm_hour * 60 + local.tm_min;
  return n;
}

int ParseHm(const std::string& hm) {
  if (hm.size() < 4) return -1;
  int h = 0, m = 0;
  try {
    h = std::stoi(hm.substr(0, 2));
    size_t colon = hm.find(':');
    if (colon != std::string::npos) m = std::stoi(hm.substr(colon + 1));
  } catch (...) {
    return -1;
  }
  return h * 60 + m;
}

bool InWindow(int cur, int start, int end) {
  if (start < 0 || end < 0) return false;
  if (start <= end) return cur >= start && cur < end;
  return cur >= start || cur < end;
}

/**
 * Is an ISO `until` stamp still in the future?
 *
 * Stamps come from two writers with different shapes: the enforcer writes bare
 * local wall clock ("…T23:59:59") and Python writes an offset
 * ("…T23:59:59+05:30"). Both mean the same instant, so a bare stamp is read as
 * local time and an offset (or "Z") is honoured. Reading everything as UTC —
 * as this did — made every free window and incubation outlive its own UI copy
 * by the whole UTC offset (5h30m here).
 */
bool IsoStillActive(const std::string& iso, std::time_t now) {
  if (iso.empty() || iso == "null") return false;

  int y = 0, mo = 0, d = 0, H = 0, M = 0, S = 0;
  if (std::sscanf(iso.c_str(), "%d-%d-%dT%d:%d:%d", &y, &mo, &d, &H, &M, &S) < 5) {
    return true;  // non-empty but unparseable: treat as still active (fail closed)
  }

  std::tm tm{};
  tm.tm_year = y - 1900;
  tm.tm_mon = mo - 1;
  tm.tm_mday = d;
  tm.tm_hour = H;
  tm.tm_min = M;
  tm.tm_sec = S;
  tm.tm_isdst = -1;

  // Look for a trailing zone marker after the time part only ('-' also appears in the date).
  int offsetMinutes = 0;
  bool hasZone = false;
  size_t tpos = iso.find('T');
  if (tpos != std::string::npos) {
    size_t z = iso.find_first_of("Zz+-", tpos);
    if (z != std::string::npos) {
      hasZone = true;
      if (iso[z] != 'Z' && iso[z] != 'z') {
        int oh = 0, om = 0;
        if (std::sscanf(iso.c_str() + z + 1, "%d:%d", &oh, &om) >= 1) {
          offsetMinutes = oh * 60 + om;
          if (iso[z] == '-') offsetMinutes = -offsetMinutes;
        }
      }
    }
  }

  std::time_t until;
  if (hasZone) {
    std::tm utc = tm;
    until = _mkgmtime(&utc);
    if (until != (std::time_t)-1) until -= (std::time_t)offsetMinutes * 60;
  } else {
    until = std::mktime(&tm);
  }
  if (until == (std::time_t)-1) return true;  // unrepresentable: keep the block on
  return until > now;
}

std::string ExtractObject(const std::string& body, const char* key) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return {};
  size_t brace = body.find('{', p);
  if (brace == std::string::npos) return {};
  int depth = 0;
  for (size_t i = brace; i < body.size(); ++i) {
    if (body[i] == '{') ++depth;
    else if (body[i] == '}') {
      --depth;
      if (depth == 0) return body.substr(brace, i - brace + 1);
    }
  }
  return {};
}

/** Text of an array value, brackets included. */
std::string ExtractArray(const std::string& body, const char* key) {
  std::string needle = std::string("\"") + key + "\"";
  size_t p = body.find(needle);
  if (p == std::string::npos) return {};
  size_t lb = body.find('[', p);
  if (lb == std::string::npos) return {};
  int depth = 0;
  bool inStr = false;
  for (size_t i = lb; i < body.size(); ++i) {
    char c = body[i];
    if (inStr) {
      if (c == '\\')
        ++i;
      else if (c == '"')
        inStr = false;
      continue;
    }
    if (c == '"')
      inStr = true;
    else if (c == '[')
      ++depth;
    else if (c == ']') {
      --depth;
      if (depth == 0) return body.substr(lb, i - lb + 1);
    }
  }
  return {};
}

/** Mon=0..Sun=6 membership; a missing or empty days list means every day. */
bool DaysInclude(const std::string& winJson, int weekday) {
  size_t daysKey = winJson.find("\"days\"");
  if (daysKey == std::string::npos) return true;
  size_t lb = winJson.find('[', daysKey);
  size_t rb = winJson.find(']', lb == std::string::npos ? 0 : lb);
  if (lb == std::string::npos || rb == std::string::npos || rb <= lb) return true;
  std::string arr = winJson.substr(lb + 1, rb - lb - 1);
  bool any = false;
  for (size_t i = 0; i < arr.size();) {
    if (!isdigit((unsigned char)arr[i])) {
      ++i;
      continue;
    }
    int num = 0;
    while (i < arr.size() && isdigit((unsigned char)arr[i])) {
      num = num * 10 + (arr[i] - '0');
      ++i;
    }
    any = true;
    if (num == weekday) return true;
  }
  return !any;
}

struct ModeFlags {
  bool block_watch_sites = true;
  bool block_porn = true;
  bool block_social = true;
  bool block_keywords = true;
  bool block_other = true;
  bool strict_allowlist = true;
};

ModeFlags FlagsForMode(const std::string& body, const std::string& mode) {
  ModeFlags f;
  if (mode == "free") {
    f.block_watch_sites = false;
    f.block_social = false;
    f.block_other = false;
    f.strict_allowlist = false;
  }
  std::string mode_flags = ExtractObject(body, "mode_flags");
  std::string section = ExtractObject(mode_flags.empty() ? body : mode_flags, mode.c_str());
  if (section.empty() && mode != "study" && mode != "free") {
    section = ExtractObject(mode_flags.empty() ? body : mode_flags, "study");
  }
  if (!section.empty()) {
    bool v = false;
    if (JsonBoolNear(section, "block_watch_sites", &v)) f.block_watch_sites = v;
    if (JsonBoolNear(section, "block_porn", &v)) f.block_porn = v;
    if (JsonBoolNear(section, "block_social", &v)) f.block_social = v;
    if (JsonBoolNear(section, "block_keywords", &v)) f.block_keywords = v;
    if (JsonBoolNear(section, "block_other", &v)) f.block_other = v;
    if (JsonBoolNear(section, "strict_allowlist", &v)) f.strict_allowlist = v;
  }
  return f;
}

std::string ResolveScheduleMode(const std::string& body, const LocalNow& now) {
  std::string schedules = ExtractObject(body, "schedules");
  bool enabled = false;
  if (!schedules.empty()) JsonBoolNear(schedules, "enabled", &enabled);
  if (!enabled) return "";

  // Iterate the windows array itself. Scanning `schedules` for '{' used to
  // match the schedules object first, so only window 1 was ever evaluated.
  std::string windows = ExtractArray(schedules, "windows");
  if (windows.empty()) return "";

  size_t pos = 1;  // skip the opening '['
  while (pos < windows.size()) {
    size_t win = windows.find('{', pos);
    if (win == std::string::npos) break;
    int depth = 0;
    size_t end = std::string::npos;
    bool inStr = false;
    for (size_t i = win; i < windows.size(); ++i) {
      char c = windows[i];
      if (inStr) {
        if (c == '\\')
          ++i;
        else if (c == '"')
          inStr = false;
        continue;
      }
      if (c == '"')
        inStr = true;
      else if (c == '{')
        ++depth;
      else if (c == '}') {
        --depth;
        if (depth == 0) {
          end = i;
          break;
        }
      }
    }
    if (end == std::string::npos) break;
    std::string w = windows.substr(win, end - win + 1);
    pos = end + 1;

    if (!DaysInclude(w, now.weekday)) continue;
    std::string start, endHm, mode;
    JsonStringNear(w, "start", &start);
    JsonStringNear(w, "end", &endHm);
    JsonStringNear(w, "mode", &mode);
    if (!InWindow(now.minutes, ParseHm(start), ParseHm(endHm))) continue;
    if (!mode.empty()) return ToLower(mode);  // first matching window wins
  }
  return "";
}

}  // namespace

std::wstring SoftlandPolicyPathW() {
  wchar_t env[MAX_PATH] = {};
  if (GetEnvironmentVariableW(L"CALT_DATA_DIR", env, MAX_PATH) > 0) {
    return JoinPath(env, L"behavior\\softland_policy.json");
  }
  if (GetEnvironmentVariableW(L"CALT_ROOT", env, MAX_PATH) > 0) {
    return JoinPath(env, L"data\\behavior\\softland_policy.json");
  }
  wchar_t mod[MAX_PATH] = {};
  GetModuleFileNameW(nullptr, mod, MAX_PATH);
  std::wstring dir = ParentDir(mod);
  for (int i = 0; i < 8; ++i) {
    std::wstring candidate = JoinPath(dir, L"data\\behavior\\softland_policy.json");
    if (FileExistsW(candidate)) return candidate;
    std::wstring next = ParentDir(dir);
    if (next == dir) break;
    dir = next;
  }
  return JoinPath(ParentDir(mod), L"data\\behavior\\softland_policy.json");
}

SoftlandModeResult SoftlandGetMode(const std::string& url, const std::string& /*now_iso_opt*/) {
  SoftlandModeResult r;
  r.schema_version = 1;
  r.action = "allow";
  r.mode = "free";
  r.reason = "ok";

  std::wstring path = SoftlandPolicyPathW();
  std::string body = ReadFileUtf8(path);
  if (body.empty()) {
    // Fail-closed: missing policy must not open the web (solo-pack).
    r.ok = true;
    r.error = "softland_policy_missing";
    r.reason = "softland_policy_missing";
    r.mode = "study";
    r.action = "block";
    r.enforce = true;
    r.interstitial = true;
    r.softland_enabled = true;
    return r;
  }

  bool enabled = false;
  if (!JsonBoolNear(body, "softland_enabled", &enabled)) {
    // Fail-closed: corrupt / unparseable policy must not open the web.
    r.ok = true;
    r.error = "softland_policy_corrupt";
    r.reason = "softland_policy_corrupt";
    r.mode = "study";
    r.action = "block";
    r.enforce = true;
    r.interstitial = true;
    r.softland_enabled = true;
    return r;
  }
  r.softland_enabled = enabled;
  if (!enabled) {
    r.ok = true;
    r.action = "allow";
    r.enforce = false;
    r.interstitial = false;
    r.reason = "softland_off";
    return r;
  }

  LocalNow now = LocalClock();
  std::string runtime = ExtractObject(body, "runtime");
  std::string free_until, incubation_until, free_after;
  bool reward_day = false;
  if (!runtime.empty()) {
    JsonStringNear(runtime, "free_until", &free_until);
    JsonStringNear(runtime, "incubation_until", &incubation_until);
    JsonStringNear(runtime, "free_after_hm", &free_after);
    JsonBoolNear(runtime, "reward_day_active", &reward_day);
  }

  bool incubating = IsoStillActive(incubation_until, now.unix);
  bool free_win = IsoStillActive(free_until, now.unix);
  if (!free_after.empty() && free_after != "null") {
    int fa = ParseHm(free_after);
    if (fa >= 0 && now.minutes >= fa) free_win = true;
  }

  std::string mode = ResolveScheduleMode(body, now);
  if (mode.empty()) mode = "study";
  if (reward_day || free_win) mode = "free";
  if (incubating) mode = "study";

  ModeFlags flags = FlagsForMode(body, mode);
  r.mode = mode;
  r.enforce = true;
  if (incubating) {
    r.until = incubation_until;
    r.reason = "incubation";
  } else if (reward_day) {
    r.reason = "reward_day";
    r.until = free_until.empty() ? free_after : free_until;
  } else if (free_win) {
    r.reason = "free_window";
    r.until = free_until.empty() ? free_after : free_until;
  }

  std::string host = HostFromUrl(url);
  if (host.empty()) {
    r.ok = true;
    r.action = "allow";
    r.reason = "no_host";
    r.enforce = false;
    return r;
  }

  std::string site_rules = ExtractObject(body, "site_rules");
  std::vector<std::string> allow_extra, watch_extra, block_extra;
  if (!site_rules.empty()) {
    ParseStringArrayNear(site_rules, "allow_extra", allow_extra);
    ParseStringArrayNear(site_rules, "watch_extra", watch_extra);
    ParseStringArrayNear(site_rules, "block_extra", block_extra);
  }

  if (ListMatch(host, allow_extra) || host == "localhost" || host == "127.0.0.1") {
    r.ok = true;
    r.action = "allow";
    r.reason = "allow_list";
    r.matched = host;
    r.interstitial = false;
    return r;
  }

  if (flags.block_porn && LooksPorn(host)) {
    r.ok = true;
    r.action = "block";
    r.enforce = true;
    if (!incubating) r.reason = "porn";
    r.matched = host;
    r.interstitial = true;
    return r;
  }

  if (ListMatch(host, block_extra)) {
    r.ok = true;
    r.action = "block";
    r.enforce = true;
    if (!incubating) r.reason = "block_extra";
    r.matched = host;
    r.interstitial = true;
    return r;
  }

  if (mode == "free" && !incubating) {
    r.ok = true;
    r.action = "allow";
    // Keep reward_day / free_window reason when already set above.
    if (r.reason.empty() || r.reason == "ok") r.reason = "free_mode";
    r.enforce = true;
    r.interstitial = false;
    return r;
  }

  if (flags.block_watch_sites) {
    if (ListMatch(host, watch_extra) || ListMatch(host, BuiltinWatch())) {
      r.ok = true;
      r.action = "block";
      r.enforce = true;
      if (!incubating) r.reason = "watch_list";
      r.matched = host;
      r.interstitial = true;
      return r;
    }
  }

  // Social subset in builtin watch already covers common social.
  if (flags.block_other && flags.strict_allowlist) {
    // Without full allowlist compiled in, only block known distractors above.
    r.ok = true;
    r.action = "allow";
    r.reason = "not_listed";
    r.interstitial = false;
    return r;
  }

  r.ok = true;
  r.action = "allow";
  r.reason = "default_allow";
  r.interstitial = false;
  return r;
}

std::string SoftlandModeResultToJson(const SoftlandModeResult& r) {
  std::ostringstream o;
  o << "{"
    << "\"schema_version\":" << r.schema_version << ","
    << "\"ok\":" << (r.ok ? "true" : "false") << ","
    << "\"action\":\"" << JsonEscape(r.action) << "\","
    << "\"mode\":\"" << JsonEscape(r.mode) << "\","
    << "\"reason\":\"" << JsonEscape(r.reason) << "\","
    << "\"softland_enabled\":" << (r.softland_enabled ? "true" : "false") << ","
    << "\"enforce\":" << (r.enforce ? "true" : "false") << ","
    << "\"interstitial\":" << (r.interstitial ? "true" : "false") << ",";
  if (r.until.empty())
    o << "\"until\":null,";
  else
    o << "\"until\":\"" << JsonEscape(r.until) << "\",";
  if (r.matched.empty())
    o << "\"matched\":null,";
  else
    o << "\"matched\":\"" << JsonEscape(r.matched) << "\",";
  if (r.redirect_url.empty())
    o << "\"redirect_url\":null";
  else
    o << "\"redirect_url\":\"" << JsonEscape(r.redirect_url) << "\"";
  if (!r.error.empty()) o << ",\"error\":\"" << JsonEscape(r.error) << "\"";
  o << "}";
  return o.str();
}
