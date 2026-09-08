#include "win_service.h"

#include <windows.h>

#include <iostream>
#include <string>

namespace {

std::wstring ExeDir() {
  wchar_t buf[MAX_PATH];
  DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring p(buf, n);
  size_t slash = p.find_last_of(L"\\/");
  return (slash == std::wstring::npos) ? L"." : p.substr(0, slash);
}

std::wstring DefaultDbPath() {
  // Prefer CALT_DB env, else ../../data/vocab_app.db from build/bin layout or repo native/../data
  wchar_t* env = _wgetenv(L"CALT_DB");
  if (env && *env) return env;
  std::wstring dir = ExeDir();
  // try repo-relative: <repo>/native/calt_enforcer/build/Release -> <repo>/data
  const wchar_t* candidates[] = {
      L"\\..\\..\\..\\..\\data\\vocab_app.db",
      L"\\..\\..\\..\\data\\vocab_app.db",
      L"\\..\\..\\data\\vocab_app.db",
      nullptr,
  };
  for (int i = 0; candidates[i]; ++i) {
    std::wstring c = dir + candidates[i];
    if (GetFileAttributesW(c.c_str()) != INVALID_FILE_ATTRIBUTES) return c;
  }
  return dir + L"\\vocab_app.db";
}

std::wstring DefaultLockPath(const std::wstring& dbPath) {
  wchar_t* env = _wgetenv(L"CALT_ENFORCER_LOCK");
  if (env && *env) return env;
  // sibling of db: data/behavior/enforcer_owner.lock
  size_t slash = dbPath.find_last_of(L"\\/");
  std::wstring dataDir = (slash == std::wstring::npos) ? L"." : dbPath.substr(0, slash);
  return dataDir + L"\\behavior\\enforcer_owner.lock";
}

void PrintUsage() {
  std::wcout
      << L"CALT Native Enforcer (C++) — zero-Python desktop tracker\n"
      << L"  calt_enforcer.exe              console loop\n"
      << L"  calt_enforcer.exe --service    Windows Service dispatcher\n"
      << L"Env: CALT_DB, CALT_ENFORCER_LOCK\n"
      << L"Policy: SQLite enforcer_runtime and/or data/behavior/enforcer_policy.json\n"
      << L"Status: data/behavior/enforcer_status.json (written every ~2.5s)\n"
      << L"Writes tracked_sessions (non-browser); holds ownership lock.\n"
      << L"No Python runtime required. No Cold Turkey code.\n";
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
  for (int i = 1; i < argc; ++i) {
    if (wcscmp(argv[i], L"--help") == 0 || wcscmp(argv[i], L"-h") == 0) {
      PrintUsage();
      return 0;
    }
  }

  std::wstring db = DefaultDbPath();
  std::wstring lock = DefaultLockPath(db);

  for (int i = 1; i < argc; ++i) {
    if (wcscmp(argv[i], L"--service") == 0) {
      return RunAsWindowsService(db, lock);
    }
  }

  std::wcout << L"CALT enforcer console. DB=" << db << L"\n";
  volatile bool stop = false;
  SetConsoleCtrlHandler(
      [](DWORD) -> BOOL {
        return TRUE;  // allow clean Ctrl+C via process kill; loop exits on close
      },
      TRUE);
  return RunEnforcerLoop(db, lock, &stop);
}
