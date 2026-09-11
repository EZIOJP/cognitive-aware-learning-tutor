#pragma once
#include <windows.h>
#include <string>

struct ForegroundInfo {
  std::wstring exe;    // basename lower, e.g. notepad.exe
  std::wstring title;  // window title (truncated)
  DWORD pid = 0;
  bool ok = false;
};

// Current foreground window process + title. ok=false if desktop/idle.
bool GetForegroundInfo(ForegroundInfo& out);
