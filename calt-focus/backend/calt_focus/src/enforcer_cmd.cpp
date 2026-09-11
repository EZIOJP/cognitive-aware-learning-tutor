#include "enforcer_cmd.h"

#include <windows.h>

#include <string>

namespace {

bool SendOnce(const std::string& jsonReq, std::string& jsonResp, unsigned timeoutMs) {
  jsonResp.clear();
  HANDLE pipe = CreateFileW(L"\\\\.\\pipe\\calt_enforcer_cmd", GENERIC_READ | GENERIC_WRITE, 0,
                            nullptr, OPEN_EXISTING, 0, nullptr);
  if (pipe == INVALID_HANDLE_VALUE) {
    if (!WaitNamedPipeW(L"\\\\.\\pipe\\calt_enforcer_cmd", timeoutMs)) {
      return false;
    }
    pipe = CreateFileW(L"\\\\.\\pipe\\calt_enforcer_cmd", GENERIC_READ | GENERIC_WRITE, 0, nullptr,
                       OPEN_EXISTING, 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return false;
  }

  DWORD mode = PIPE_READMODE_MESSAGE;
  SetNamedPipeHandleState(pipe, &mode, nullptr, nullptr);

  DWORD written = 0;
  if (!WriteFile(pipe, jsonReq.data(), (DWORD)jsonReq.size(), &written, nullptr)) {
    CloseHandle(pipe);
    return false;
  }

  char buf[64 * 1024];
  DWORD read = 0;
  if (!ReadFile(pipe, buf, sizeof(buf) - 1, &read, nullptr) || read == 0) {
    CloseHandle(pipe);
    return false;
  }
  buf[read] = 0;
  jsonResp.assign(buf, read);
  CloseHandle(pipe);
  return true;
}

}  // namespace

bool EnforcerSendCommand(const std::string& jsonReq, std::string& jsonResp, unsigned timeoutMs) {
  // The enforcer serves one pipe instance from its tick loop: connecting while
  // it recycles the instance can break once, so retry before giving up (a
  // false failure here would silently push the UI onto the HTTP fallback).
  for (int attempt = 0; attempt < 3; ++attempt) {
    if (SendOnce(jsonReq, jsonResp, timeoutMs)) return true;
    Sleep(120);
  }
  return false;
}
