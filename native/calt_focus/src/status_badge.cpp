#include "status_badge.h"

#include "paths.h"

#include <fstream>
#include <sstream>

namespace {

bool JsonBool(const std::string& body, const char* key, bool def = false) {
  const std::string needle = std::string("\"") + key + "\"";
  const auto pos = body.find(needle);
  if (pos == std::string::npos) {
    return def;
  }
  const auto colon = body.find(':', pos + needle.size());
  if (colon == std::string::npos) {
    return def;
  }
  const auto t = body.find("true", colon);
  const auto f = body.find("false", colon);
  if (t != std::string::npos && (f == std::string::npos || t < f)) {
    // ensure within ~32 chars of colon
    if (t - colon < 32) {
      return true;
    }
  }
  if (f != std::string::npos && f - colon < 32) {
    return false;
  }
  return def;
}

std::wstring JsonString(const std::string& body, const char* key) {
  const std::string needle = std::string("\"") + key + "\"";
  const auto pos = body.find(needle);
  if (pos == std::string::npos) {
    return L"";
  }
  const auto colon = body.find(':', pos + needle.size());
  if (colon == std::string::npos) {
    return L"";
  }
  const auto q1 = body.find('"', colon + 1);
  if (q1 == std::string::npos) {
    return L"";
  }
  const auto q2 = body.find('"', q1 + 1);
  if (q2 == std::string::npos || q2 <= q1 + 1) {
    return L"";
  }
  const std::string raw = body.substr(q1 + 1, q2 - q1 - 1);
  if (raw.empty()) {
    return L"";
  }
  return std::wstring(raw.begin(), raw.end());
}

}  // namespace

EnforcerBadge ReadEnforcerBadge() {
  EnforcerBadge b;
  const std::wstring path = EnforcerStatusPath();
  std::ifstream in(path.c_str());
  if (!in) {
    return b;
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string body = ss.str();
  if (body.empty()) {
    return b;
  }
  b.ok = true;
  b.owns = JsonBool(body, "owns");
  b.armed = JsonBool(body, "armed");
  b.softland_or_armed = JsonBool(body, "softland_or_armed");
  b.service_running = JsonBool(body, "service_running");
  b.last_kill_exe = JsonString(body, "last_kill_exe");
  if (b.last_kill_exe.empty()) {
    b.last_kill_exe = JsonString(body, "last_kill");
  }
  return b;
}

bool FocusBlocksActive() {
  const EnforcerBadge b = ReadEnforcerBadge();
  if (b.ok && b.softland_or_armed) {
    return true;
  }
  if (b.ok && b.armed) {
    return true;
  }
  // SoftLand SoT: softland_policy.json (status may lag one tick).
  const std::wstring path = SoftlandPolicyPath();
  std::ifstream in(path.c_str());
  if (!in) {
    return b.armed;
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return JsonBool(ss.str(), "softland_enabled") || b.armed;
}

std::wstring FormatTrayTooltip(const EnforcerBadge& b) {
  if (!b.ok) {
    return L"CALT Focus — enforcer status unavailable";
  }
  std::wstring tip = L"CALT Focus";
  tip += b.owns ? L" · owns" : L" · no lock";
  tip += b.armed ? L" · armed" : L" · disarmed";
  if (!b.last_kill_exe.empty()) {
    tip += L" · last ";
    tip += b.last_kill_exe;
  }
  return tip;
}
