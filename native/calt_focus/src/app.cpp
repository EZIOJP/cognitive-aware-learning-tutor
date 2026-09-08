#include <winsock2.h>
#include <ws2tcpip.h>

#include "app.h"

#include "paths.h"
#include "status_badge.h"

#include <objbase.h>
#include <shellapi.h>

#include <string>

namespace {

constexpr wchar_t kMainClass[] = L"CALTFocusMain";
constexpr wchar_t kMsgClass[] = L"CALTFocusMsg";
constexpr UINT kTipTimerId = 77;

bool AlreadyRunning() {
  HANDLE mutex = CreateMutexW(nullptr, FALSE, L"Local\\CALT.FocusShell.A");
  if (!mutex) {
    return false;
  }
  return GetLastError() == ERROR_ALREADY_EXISTS;
}

void ActivateExisting() {
  HWND hwnd = FindWindowW(kMainClass, nullptr);
  if (hwnd) {
    ShowWindow(hwnd, SW_SHOW);
    SetForegroundWindow(hwnd);
  }
}

std::wstring PythonExe() {
  const std::wstring venv = RepoRoot() + L"\\.venv\\Scripts\\python.exe";
  if (GetFileAttributesW(venv.c_str()) != INVALID_FILE_ATTRIBUTES) {
    return venv;
  }
  return L"python";
}

}  // namespace

int FocusApp::Run(HINSTANCE instance) {
  instance_ = instance;
  if (AlreadyRunning()) {
    ActivateExisting();
    return 0;
  }

  WSADATA wsa{};
  WSAStartup(MAKEWORD(2, 2), &wsa);

  CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  CreateMessageWindow(instance);
  CreateMainWindow(instance);

  tray_ = std::make_unique<TrayIcon>();
  HICON icon = MakeDotIcon();
  tray_->Create(msg_hwnd_, icon, L"CALT Focus");
  tray_->SetOnRun([this]() { RunStack(); });
  tray_->SetOnStartStack([this]() { StartWebStack(); });
  tray_->SetOnStartApi([this]() { StartApiOnly(); });
  tray_->SetOnStartFe([this]() { StartFrontendOnly(); });
  tray_->SetOnOpen([this]() { ShowFocusWindow(); });
  tray_->SetOnSettings([this]() { OpenSettings(); });
  tray_->SetOnCalendar([this]() { OpenCalendar(); });
  tray_->SetOnPlan([this]() { OpenPlan(); });
  tray_->SetOnProductivity([this]() { OpenCalendar(); });
  tray_->SetOnQuit([this]() { Quit(); });

  webview_ = std::make_unique<WebViewHost>();
  pending_url_ = CalendarUrl();
  webview_->Init(main_hwnd_, WebViewUserDataDir(), [this](bool ok) {
    webview_failed_ = !ok;
    if (ok) {
      ShowWindow(main_hwnd_, SW_SHOW);
      SetForegroundWindow(main_hwnd_);
      if (HasPrebuiltWebUi()) {
        if (EnsurePrebuiltUiReady()) {
          pending_url_ = CalendarUrl();
          webview_->Navigate(pending_url_);
          if (!PortListening(8000)) {
            if (tray_) {
              tray_->ShowBalloon(
                  L"CALT Focus",
                  L"Prebuilt UI ready. Starting API (:8000)…");
            }
            StartApiOnly();
            ShowFocusWindow();
          }
        } else {
          ShowOfflinePage();
        }
      } else if (PortListening(5173)) {
        webview_->Navigate(pending_url_);
      } else {
        ShowOfflinePage();
        if (tray_) {
          tray_->ShowBalloon(
              L"CALT Focus",
              L"No prebuilt UI — run npm run build:focus once");
        }
      }
    } else {
      ShellExecuteW(nullptr, L"open", pending_url_.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
      MessageBoxW(
          nullptr,
          L"WebView2 failed to start.\n\n"
          L"Install the Evergreen WebView2 Runtime.\n"
          L"Tray → Run to start API / open Focus.",
          L"CALT Focus",
          MB_OK | MB_ICONWARNING);
    }
  });

  tip_timer_ = SetTimer(msg_hwnd_, kTipTimerId, 2500, nullptr);
  RefreshTrayTip();

  MSG msg{};
  while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
    TranslateMessage(&msg);
    DispatchMessageW(&msg);
  }

  if (tip_timer_) {
    KillTimer(msg_hwnd_, tip_timer_);
  }
  tray_.reset();
  webview_.reset();
  CoUninitialize();
  WSACleanup();
  return 0;
}

void FocusApp::CreateMainWindow(HINSTANCE instance) {
  WNDCLASSEXW wc{};
  wc.cbSize = sizeof(wc);
  wc.lpfnWndProc = FocusApp::WndProc;
  wc.hInstance = instance;
  wc.lpszClassName = kMainClass;
  wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
  RegisterClassExW(&wc);

  main_hwnd_ = CreateWindowExW(
      0, kMainClass, L"CALT Focus", WS_OVERLAPPEDWINDOW,
      CW_USEDEFAULT, CW_USEDEFAULT, 1100, 740,
      nullptr, nullptr, instance, this);
}

void FocusApp::CreateMessageWindow(HINSTANCE instance) {
  WNDCLASSEXW wc{};
  wc.cbSize = sizeof(wc);
  wc.lpfnWndProc = FocusApp::WndProc;
  wc.hInstance = instance;
  wc.lpszClassName = kMsgClass;
  RegisterClassExW(&wc);

  msg_hwnd_ = CreateWindowExW(
      0, kMsgClass, L"CALT Focus Tray", 0,
      0, 0, 0, 0, HWND_MESSAGE, nullptr, instance, this);
}

LRESULT CALLBACK FocusApp::WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
  FocusApp* self = nullptr;
  if (msg == WM_NCCREATE) {
    auto* cs = reinterpret_cast<CREATESTRUCTW*>(lParam);
    self = static_cast<FocusApp*>(cs->lpCreateParams);
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
  } else {
    self = reinterpret_cast<FocusApp*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
  }
  if (!self) {
    return DefWindowProcW(hwnd, msg, wParam, lParam);
  }
  return self->HandleMessage(hwnd, msg, wParam, lParam);
}

LRESULT FocusApp::HandleMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
  if (hwnd == msg_hwnd_ && tray_) {
    if (msg == TrayIcon::WM_TRAY || msg == WM_COMMAND) {
      tray_->HandleMessage(msg, wParam, lParam);
      return 0;
    }
    if (msg == WM_TIMER && wParam == kTipTimerId) {
      RefreshTrayTip();
      return 0;
    }
  }

  switch (msg) {
    case WM_SIZE:
      if (webview_) {
        webview_->Resize();
      }
      return 0;
    case WM_CLOSE:
      // Hide to tray instead of quit
      ShowWindow(main_hwnd_, SW_HIDE);
      return 0;
    case WM_DESTROY:
      if (hwnd == main_hwnd_) {
        // only quit via tray Quit
        return 0;
      }
      break;
    default:
      break;
  }
  return DefWindowProcW(hwnd, msg, wParam, lParam);
}

void FocusApp::ShowFocusWindow() {
  if (!main_hwnd_) {
    return;
  }
  if (webview_ && webview_->Ready()) {
    if (HasPrebuiltWebUi()) {
      if (EnsurePrebuiltUiReady()) {
        webview_->Navigate(FocusUrl());
      } else {
        ShowOfflinePage();
      }
    } else if (PortListening(5173)) {
      webview_->Navigate(FocusUrl());
    } else {
      ShowOfflinePage();
    }
  } else if (webview_failed_) {
    ShellExecuteW(nullptr, L"open", FocusUrl().c_str(), nullptr, nullptr, SW_SHOWNORMAL);
    return;
  }
  ShowWindow(main_hwnd_, SW_SHOW);
  ShowWindow(main_hwnd_, SW_RESTORE);
  SetForegroundWindow(main_hwnd_);
}

void FocusApp::ShowOfflinePage() {
  if (!webview_ || !webview_->Ready()) {
    return;
  }
  const wchar_t* html =
      L"data:text/html;charset=utf-8,"
      L"%3Chtml%3E%3Cbody%20style%3D'font-family:Segoe%20UI%2Csans-serif%3B"
      L"background%3A%230f172a%3Bcolor%3A%23e2e8f0%3Bpadding%3A32px'%3E"
      L"%3Ch2%3ECALT%20Focus%20%E2%80%94%20UI%20not%20ready%3C%2Fh2%3E"
      L"%3Cp%3EBuild%20precompiled%20UI%20once%20(no%20Vite%20daily)%3A%3C%2Fp%3E"
      L"%3Cpre%20style%3D'background%3A%231e293b%3Bpadding%3A12px'%3Enpm%20run%20build%3Afocus%3C%2Fpre%3E"
      L"%3Cp%3EThen%20reopen%20CALT%20Focus.%20API%20%3A8000%20only%20for%20live%20data.%3C%2Fp%3E"
      L"%3C%2Fbody%3E%3C%2Fhtml%3E";
  webview_->Navigate(html);
}

bool FocusApp::EnsureFocusStaticServer() {
  if (PortListening(5174)) {
    return true;
  }
  const std::wstring root = RepoRoot();
  const std::wstring py = PythonExe();
  const std::wstring script = root + L"\\scripts\\serve_focus_ui.py";
  std::wstring cmdLine = L"\"" + py + L"\" \"" + script + L"\"";
  STARTUPINFOW si{};
  si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  std::wstring mutableCmd = cmdLine;
  const BOOL ok = CreateProcessW(
      nullptr,
      mutableCmd.data(),
      nullptr,
      nullptr,
      FALSE,
      CREATE_NO_WINDOW,
      nullptr,
      root.c_str(),
      &si,
      &pi);
  if (!ok) {
    return false;
  }
  CloseHandle(pi.hThread);
  CloseHandle(pi.hProcess);
  return WaitForPort(5174, 20000);
}

bool FocusApp::EnsurePrebuiltUiReady() {
  if (!webview_ || !webview_->Ready() || !HasPrebuiltWebUi()) {
    return false;
  }
  // 1) WebView2 virtual host https://calt.app → dist-focus (ES modules work)
  if (webview_->MapStaticSite(DistDir())) {
    // Solo-pack: SoftLand / status JSON readable without :8000
    webview_->MapBehaviorData(DataBehaviorDir());
    SetEnvironmentVariableW(L"CALT_FOCUS_UI_MODE", nullptr);
    return true;
  }
  // 2) Fallback: local static server (still no Vite)
  if (EnsureFocusStaticServer()) {
    SetEnvironmentVariableW(L"CALT_FOCUS_UI_MODE", L"static");
    if (tray_) {
      tray_->ShowBalloon(
          L"CALT Focus",
          L"Using local prebuilt UI on :5174 (no Vite).");
    }
    return true;
  }
  return false;
}

bool FocusApp::PortListening(unsigned short port) {
  SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET) {
    return false;
  }
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
  // Non-blocking short connect
  u_long nonblock = 1;
  ioctlsocket(s, FIONBIO, &nonblock);
  const int r = connect(s, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
  bool ok = false;
  if (r == 0) {
    ok = true;
  } else if (WSAGetLastError() == WSAEWOULDBLOCK) {
    fd_set w{};
    FD_ZERO(&w);
    FD_SET(s, &w);
    timeval tv{};
    tv.tv_sec = 0;
    tv.tv_usec = 200000;
    ok = select(0, nullptr, &w, nullptr, &tv) > 0;
  }
  closesocket(s);
  return ok;
}

bool FocusApp::WaitForPort(unsigned short port, DWORD timeoutMs) {
  const DWORD start = GetTickCount();
  while (GetTickCount() - start < timeoutMs) {
    if (PortListening(port)) {
      return true;
    }
    Sleep(400);
    MSG pump{};
    while (PeekMessageW(&pump, nullptr, 0, 0, PM_REMOVE)) {
      TranslateMessage(&pump);
      DispatchMessageW(&pump);
    }
  }
  return PortListening(port);
}

bool FocusApp::RunLifecycleCommand(const wchar_t* command, bool wait) {
  const std::wstring root = RepoRoot();
  const std::wstring py = PythonExe();
  const std::wstring script = root + L"\\scripts\\server_lifecycle.py";
  std::wstring cmdLine = L"\"" + py + L"\" \"" + script + L"\" ";
  cmdLine += command;

  STARTUPINFOW si{};
  si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  std::wstring mutableCmd = cmdLine;
  const BOOL ok = CreateProcessW(
      nullptr,
      mutableCmd.data(),
      nullptr,
      nullptr,
      FALSE,
      CREATE_NEW_CONSOLE,
      nullptr,
      root.c_str(),
      &si,
      &pi);
  if (!ok) {
    // Fallback: run.bat for full stack
    if (wcscmp(command, L"ensure-fast") == 0) {
      const std::wstring bat = root + L"\\run.bat";
      ShellExecuteW(nullptr, L"open", bat.c_str(), nullptr, root.c_str(), SW_SHOW);
      return true;
    }
    return false;
  }
  if (wait) {
    // Pump UI while waiting so tray stays responsive
    while (WaitForSingleObject(pi.hProcess, 200) == WAIT_TIMEOUT) {
      MSG pump{};
      while (PeekMessageW(&pump, nullptr, 0, 0, PM_REMOVE)) {
        TranslateMessage(&pump);
        DispatchMessageW(&pump);
      }
    }
  }
  CloseHandle(pi.hThread);
  CloseHandle(pi.hProcess);
  return true;
}

void FocusApp::EnsureEnforcer() {
  SC_HANDLE scm = OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CONNECT);
  if (scm) {
    SC_HANDLE svc = OpenServiceW(scm, L"CALTEnforcer", SERVICE_QUERY_STATUS | SERVICE_START);
    if (svc) {
      SERVICE_STATUS st{};
      if (QueryServiceStatus(svc, &st) && st.dwCurrentState == SERVICE_RUNNING) {
        CloseServiceHandle(svc);
        CloseServiceHandle(scm);
        return;
      }
      StartServiceW(svc, 0, nullptr);
      CloseServiceHandle(svc);
      CloseServiceHandle(scm);
      return;
    }
    CloseServiceHandle(scm);
  }

  const std::wstring root = RepoRoot();
  const std::wstring ps1 = root + L"\\scripts\\desktop_tracker\\install_enforcer_service.ps1";
  const std::wstring args = L"-NoProfile -ExecutionPolicy Bypass -File \"" + ps1 + L"\" -Start";
  SHELLEXECUTEINFOW sei{};
  sei.cbSize = sizeof(sei);
  sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI;
  sei.lpVerb = L"open";
  sei.lpFile = L"powershell.exe";
  sei.lpParameters = args.c_str();
  sei.nShow = SW_HIDE;
  if (ShellExecuteExW(&sei)) {
    if (sei.hProcess) {
      WaitForSingleObject(sei.hProcess, 15000);
      CloseHandle(sei.hProcess);
    }
    return;
  }

  const std::wstring console = root + L"\\scripts\\desktop_tracker\\run_native_enforcer_console.bat";
  ShellExecuteW(nullptr, L"open", console.c_str(), nullptr, root.c_str(), SW_SHOWMINNOACTIVE);
}

void FocusApp::StartWebStack() {
  if (tray_) {
    tray_->ShowBalloon(L"CALT Focus", L"Starting API (:8000) + Frontend (:5173)…");
  }
  RunLifecycleCommand(L"ensure-fast", true);
  const bool up = WaitForPort(5173, 90000);
  if (up) {
    OpenCalendar();
    if (tray_) {
      tray_->ShowBalloon(L"CALT Focus", L"Web stack is up — Calendar loaded.");
    }
  } else if (tray_) {
    tray_->ShowBalloon(
        L"CALT Focus",
        L"Still waiting on :5173. Check the server console, then Open Calendar.");
    ShowOfflinePage();
  }
  RefreshTrayTip();
}

void FocusApp::StartApiOnly() {
  if (tray_) {
    tray_->ShowBalloon(L"CALT Focus", L"Starting API (:8000)…");
  }
  RunLifecycleCommand(L"ensure-api", true);
  WaitForPort(8000, 60000);
  RefreshTrayTip();
  if (tray_) {
    tray_->ShowBalloon(
        L"CALT Focus",
        PortListening(8000) ? L"API is up on :8000." : L"API not reachable yet — check console.");
  }
}

void FocusApp::StartFrontendOnly() {
  if (tray_) {
    tray_->ShowBalloon(L"CALT Focus", L"Starting Frontend (Vite :5173)…");
  }
  RunLifecycleCommand(L"ensure-frontend", true);
  const bool up = WaitForPort(5173, 90000);
  if (up) {
    OpenCalendar();
  } else {
    ShowOfflinePage();
  }
  RefreshTrayTip();
  if (tray_) {
    tray_->ShowBalloon(
        L"CALT Focus",
        up ? L"Frontend is up — Calendar loaded." : L"Frontend not up yet — check console.");
  }
}

void FocusApp::RunStack() {
  EnsureEnforcer();
  if (HasPrebuiltWebUi()) {
    // Precompiled dist/ — only need API for live Arm/Disarm data.
    if (!PortListening(8000)) {
      StartApiOnly();
    }
    OpenCalendar();
    if (tray_) {
      tray_->ShowBalloon(
          L"CALT Focus",
          L"Prebuilt UI + enforcer. Calendar ready.");
    }
    return;
  }
  StartWebStack();
}

void FocusApp::OpenProductivity() {
  NavigateShell(ProductivityUrl());
}

void FocusApp::OpenSettings() {
  NavigateShell(SettingsUrl());
}

void FocusApp::OpenCalendar() {
  NavigateShell(CalendarUrl());
}

void FocusApp::OpenPlan() {
  NavigateShell(PlanUrl());
}

void FocusApp::NavigateShell(const std::wstring& url) {
  if (HasPrebuiltWebUi()) {
    if (!PortListening(8000)) {
      StartApiOnly();
    }
    if (webview_ && webview_->Ready() && EnsurePrebuiltUiReady()) {
      webview_->Navigate(url);
      ShowWindow(main_hwnd_, SW_SHOW);
      SetForegroundWindow(main_hwnd_);
      return;
    }
  }
  if (!PortListening(5173)) {
    StartWebStack();
  }
  ShellExecuteW(nullptr, L"open", url.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
}

void FocusApp::Quit() {
  // Solo-pack: tray Quit only when SoftLand off and Disarmed (else enforcer relaunches).
  if (FocusBlocksActive()) {
    if (tray_) {
      tray_->ShowBalloon(
          L"CALT Focus",
          L"Turn SoftLand off and Disarm hard-block before Quit (or unlock while armed).");
    }
    return;
  }
  if (tray_) {
    tray_->Destroy();
  }
  if (main_hwnd_) {
    DestroyWindow(main_hwnd_);
  }
  if (msg_hwnd_) {
    DestroyWindow(msg_hwnd_);
  }
  PostQuitMessage(0);
}

void FocusApp::RefreshTrayTip() {
  if (!tray_) {
    return;
  }
  const EnforcerBadge b = ReadEnforcerBadge();
  tray_->SetTooltip(FormatTrayTooltip(b).c_str());

  // Toast when enforcer records a new kill (apps SoftLand/hard-block).
  if (!b.last_kill_exe.empty()) {
    if (!kill_toast_primed_) {
      last_kill_toast_ = b.last_kill_exe;
      kill_toast_primed_ = true;
    } else if (b.last_kill_exe != last_kill_toast_) {
      last_kill_toast_ = b.last_kill_exe;
      std::wstring body = L"Closed: " + b.last_kill_exe + L" — hard block is armed.";
      tray_->ShowBalloon(L"CALT blocked an app", body.c_str());
    }
  }
}

HICON FocusApp::MakeDotIcon() {
  const int s = 64;
  BITMAPINFO bmi{};
  bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  bmi.bmiHeader.biWidth = s;
  bmi.bmiHeader.biHeight = -s;
  bmi.bmiHeader.biPlanes = 1;
  bmi.bmiHeader.biBitCount = 32;
  bmi.bmiHeader.biCompression = BI_RGB;
  void* bits = nullptr;
  HDC hdc = GetDC(nullptr);
  HBITMAP dib = CreateDIBSection(hdc, &bmi, DIB_RGB_COLORS, &bits, nullptr, 0);
  ReleaseDC(nullptr, hdc);
  if (!dib || !bits) {
    return LoadIcon(nullptr, IDI_APPLICATION);
  }
  auto* px = static_cast<unsigned char*>(bits);
  for (int y = 0; y < s; ++y) {
    for (int x = 0; x < s; ++x) {
      const int dx = x - 32;
      const int dy = y - 32;
      const int idx = (y * s + x) * 4;
      if (dx * dx + dy * dy <= 24 * 24) {
        px[idx + 0] = 166;  // B teal-ish
        px[idx + 1] = 184;
        px[idx + 2] = 20;
        px[idx + 3] = 255;
      } else {
        px[idx + 0] = 0;
        px[idx + 1] = 0;
        px[idx + 2] = 0;
        px[idx + 3] = 0;
      }
    }
  }
  HBITMAP mask = CreateBitmap(s, s, 1, 1, nullptr);
  ICONINFO ii{};
  ii.fIcon = TRUE;
  ii.hbmMask = mask;
  ii.hbmColor = dib;
  HICON icon = CreateIconIndirect(&ii);
  DeleteObject(mask);
  DeleteObject(dib);
  return icon ? icon : LoadIcon(nullptr, IDI_APPLICATION);
}
