#pragma once

#include <string>

struct SoftlandModeResult {
  bool ok = false;
  int schema_version = 1;
  std::string action;   // allow | block | none
  std::string mode;     // study | free | planning | bible
  std::string reason;
  bool softland_enabled = false;
  bool enforce = false;
  bool interstitial = false;
  std::string until;    // ISO or empty
  std::string matched;
  std::string redirect_url;
  std::string error;
};

/** Decide SoftLand for url using data/behavior/softland_policy.json. No Python. */
SoftlandModeResult SoftlandGetMode(const std::string& url, const std::string& now_iso_opt);

/** Resolve path to softland_policy.json (env CALT_DATA_DIR / CALT_ROOT / walk from exe). */
std::wstring SoftlandPolicyPathW();

std::string SoftlandModeResultToJson(const SoftlandModeResult& r);
