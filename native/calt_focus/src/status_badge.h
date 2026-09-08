#pragma once

#include <string>

// Best-effort read of enforcer_status.json (UI badge only — no kills).

struct EnforcerBadge {
  bool owns = false;
  bool armed = false;
  bool softland_or_armed = false;
  bool service_running = false;
  std::wstring last_kill_exe;
  bool ok = false;
};

EnforcerBadge ReadEnforcerBadge();
/** SoftLand on or hard-block armed — Focus Quit is refused while true. */
bool FocusBlocksActive();
std::wstring FormatTrayTooltip(const EnforcerBadge& b);
