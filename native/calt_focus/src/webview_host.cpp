#include "webview_host.h"
#include "enforcer_cmd.h"

#include <WebView2.h>
#include <shlwapi.h>

#include <atomic>
#include <functional>
#include <string>

namespace {

class EnvHandler : public ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler {
 public:
  explicit EnvHandler(std::function<void(HRESULT, ICoreWebView2Environment*)> cb)
      : cb_(std::move(cb)) {}

  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
    if (!ppv) {
      return E_POINTER;
    }
    if (riid == IID_IUnknown ||
        riid == IID_ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler) {
      *ppv = static_cast<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*>(this);
      AddRef();
      return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
  }
  ULONG STDMETHODCALLTYPE AddRef() override { return ++ref_; }
  ULONG STDMETHODCALLTYPE Release() override {
    const ULONG n = --ref_;
    if (n == 0) {
      delete this;
    }
    return n;
  }
  HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                   ICoreWebView2Environment* createdEnvironment) override {
    cb_(errorCode, createdEnvironment);
    return S_OK;
  }

 private:
  std::function<void(HRESULT, ICoreWebView2Environment*)> cb_;
  std::atomic<ULONG> ref_{1};
};

class CtrlHandler : public ICoreWebView2CreateCoreWebView2ControllerCompletedHandler {
 public:
  explicit CtrlHandler(std::function<void(HRESULT, ICoreWebView2Controller*)> cb)
      : cb_(std::move(cb)) {}

  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
    if (!ppv) {
      return E_POINTER;
    }
    if (riid == IID_IUnknown ||
        riid == IID_ICoreWebView2CreateCoreWebView2ControllerCompletedHandler) {
      *ppv = static_cast<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler*>(this);
      AddRef();
      return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
  }
  ULONG STDMETHODCALLTYPE AddRef() override { return ++ref_; }
  ULONG STDMETHODCALLTYPE Release() override {
    const ULONG n = --ref_;
    if (n == 0) {
      delete this;
    }
    return n;
  }
  HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                   ICoreWebView2Controller* createdController) override {
    cb_(errorCode, createdController);
    return S_OK;
  }

 private:
  std::function<void(HRESULT, ICoreWebView2Controller*)> cb_;
  std::atomic<ULONG> ref_{1};
};

using CreateEnvFn = HRESULT(STDMETHODCALLTYPE*)(
    PCWSTR browserExecutableFolder, PCWSTR userDataFolder,
    ICoreWebView2EnvironmentOptions* environmentOptions,
    ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler* environmentCreatedHandler);

HMODULE LoadWebView2Loader() {
  wchar_t exe[MAX_PATH] = {};
  GetModuleFileNameW(nullptr, exe, MAX_PATH);
  PathRemoveFileSpecW(exe);
  const std::wstring beside = std::wstring(exe) + L"\\WebView2Loader.dll";
  if (HMODULE m = LoadLibraryW(beside.c_str())) {
    return m;
  }
  return LoadLibraryW(L"WebView2Loader.dll");
}

std::wstring WidenUtf8(const std::string& s) {
  if (s.empty()) return {};
  int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
  std::wstring w(n, L'\0');
  MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), w.data(), n);
  return w;
}

std::string NarrowUtf8(const std::wstring& w) {
  if (w.empty()) return {};
  int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  std::string s(n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), s.data(), n, nullptr, nullptr);
  return s;
}

class MsgHandler : public ICoreWebView2WebMessageReceivedEventHandler {
 public:
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override {
    if (!ppv) return E_POINTER;
    if (riid == IID_IUnknown || riid == IID_ICoreWebView2WebMessageReceivedEventHandler) {
      *ppv = static_cast<ICoreWebView2WebMessageReceivedEventHandler*>(this);
      AddRef();
      return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
  }
  ULONG STDMETHODCALLTYPE AddRef() override { return ++ref_; }
  ULONG STDMETHODCALLTYPE Release() override {
    const ULONG n = --ref_;
    if (n == 0) delete this;
    return n;
  }
  HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2* sender,
                                   ICoreWebView2WebMessageReceivedEventArgs* args) override {
    if (!sender || !args) return S_OK;
    LPWSTR json = nullptr;
    if (FAILED(args->get_WebMessageAsJson(&json)) || !json) return S_OK;
    std::string msg = NarrowUtf8(json);
    CoTaskMemFree(json);

    // Expect: {"type":"enforcer_cmd","id":"...","op":"...","payload":{...},"v":1}
    if (msg.find("\"enforcer_cmd\"") == std::string::npos) return S_OK;

    std::string id, op;
    auto grab = [&](const char* key, std::string* out) {
      std::string needle = std::string("\"") + key + "\"";
      size_t p = msg.find(needle);
      if (p == std::string::npos) return;
      size_t colon = msg.find(':', p + needle.size());
      if (colon == std::string::npos) return;
      size_t i = colon + 1;
      while (i < msg.size() && (msg[i] == ' ' || msg[i] == '\t')) ++i;
      if (i >= msg.size() || msg[i] != '"') return;
      ++i;
      std::string val;
      while (i < msg.size() && msg[i] != '"') {
        if (msg[i] == '\\' && i + 1 < msg.size()) {
          val.push_back(msg[i + 1]);
          i += 2;
          continue;
        }
        val.push_back(msg[i++]);
      }
      *out = val;
    };
    grab("id", &id);
    grab("op", &op);

    std::string payload = "{}";
    {
      size_t p = msg.find("\"payload\"");
      if (p != std::string::npos) {
        size_t colon = msg.find(':', p + 9);
        if (colon != std::string::npos) {
          size_t i = colon + 1;
          while (i < msg.size() && (msg[i] == ' ' || msg[i] == '\t')) ++i;
          if (i < msg.size() && msg[i] == '{') {
            int depth = 0;
            size_t start = i;
            for (; i < msg.size(); ++i) {
              if (msg[i] == '{')
                ++depth;
              else if (msg[i] == '}') {
                --depth;
                if (depth == 0) {
                  payload = msg.substr(start, i - start + 1);
                  break;
                }
              }
            }
          }
        }
      }
    }

    std::string req = std::string("{\"op\":\"") + op + "\",\"v\":1,\"id\":\"" + id +
                      "\",\"payload\":" + payload + "}";
    std::string resp;
    std::string out;
    if (!EnforcerSendCommand(req, resp)) {
      out = std::string("{\"type\":\"enforcer_cmd_result\",\"ok\":false,\"id\":\"") + id +
            "\",\"error\":\"enforcer_unreachable\"}";
    } else if (!resp.empty() && resp[0] == '{') {
      out = std::string("{\"type\":\"enforcer_cmd_result\",") + resp.substr(1);
    } else {
      out = std::string("{\"type\":\"enforcer_cmd_result\",\"ok\":false,\"id\":\"") + id +
            "\",\"error\":\"bad_response\"}";
    }
    std::wstring w = WidenUtf8(out);
    sender->PostWebMessageAsJson(w.c_str());
    return S_OK;
  }

 private:
  std::atomic<ULONG> ref_{1};
};

}  // namespace

WebViewHost::WebViewHost() = default;

WebViewHost::~WebViewHost() {
  if (webview_) {
    webview_->Release();
    webview_ = nullptr;
  }
  if (controller_) {
    controller_->Close();
    controller_->Release();
    controller_ = nullptr;
  }
  if (loader_) {
    FreeLibrary(loader_);
    loader_ = nullptr;
  }
}

bool WebViewHost::Init(HWND parent, const std::wstring& userDataDir, ReadyFn onReady) {
  parent_ = parent;
  user_data_ = userDataDir;
  on_ready_ = std::move(onReady);

  loader_ = LoadWebView2Loader();
  if (!loader_) {
    if (on_ready_) {
      on_ready_(false);
    }
    return false;
  }

  auto createEnv = reinterpret_cast<CreateEnvFn>(
      GetProcAddress(loader_, "CreateCoreWebView2EnvironmentWithOptions"));
  if (!createEnv) {
    if (on_ready_) {
      on_ready_(false);
    }
    return false;
  }

  auto* handler = new EnvHandler([this](HRESULT hr, ICoreWebView2Environment* env) {
    OnEnvironment(hr, env);
  });
  const HRESULT hr = createEnv(nullptr, user_data_.c_str(), nullptr, handler);
  handler->Release();
  if (FAILED(hr)) {
    if (on_ready_) {
      on_ready_(false);
    }
    return false;
  }
  return true;
}

void WebViewHost::OnEnvironment(HRESULT hr, void* envVoid) {
  auto* env = static_cast<ICoreWebView2Environment*>(envVoid);
  if (FAILED(hr) || !env) {
    if (on_ready_) {
      on_ready_(false);
    }
    return;
  }
  auto* handler = new CtrlHandler([this](HRESULT ehr, ICoreWebView2Controller* ctrl) {
    OnController(ehr, ctrl);
  });
  const HRESULT chr = env->CreateCoreWebView2Controller(parent_, handler);
  handler->Release();
  if (FAILED(chr)) {
    if (on_ready_) {
      on_ready_(false);
    }
  }
}

void WebViewHost::OnController(HRESULT hr, ICoreWebView2Controller* controller) {
  if (FAILED(hr) || !controller) {
    if (on_ready_) {
      on_ready_(false);
    }
    return;
  }
  controller_ = controller;
  controller_->AddRef();

  ICoreWebView2* wv = nullptr;
  if (FAILED(controller_->get_CoreWebView2(&wv)) || !wv) {
    if (on_ready_) {
      on_ready_(false);
    }
    return;
  }
  webview_ = wv;
  Resize();
  controller_->put_IsVisible(TRUE);
  {
    EventRegistrationToken token{};
    auto* msg = new MsgHandler();
    webview_->add_WebMessageReceived(msg, &token);
    msg->Release();
  }
  ready_ = true;
  if (on_ready_) {
    on_ready_(true);
  }
}

bool WebViewHost::MapStaticSite(const std::wstring& folderAbsolute) {
  if (!webview_ || folderAbsolute.empty()) {
    return false;
  }
  ICoreWebView2_3* wv3 = nullptr;
  if (FAILED(webview_->QueryInterface(IID_ICoreWebView2_3, reinterpret_cast<void**>(&wv3))) ||
      !wv3) {
    return false;
  }
  const HRESULT hr = wv3->SetVirtualHostNameToFolderMapping(
      L"calt.app",
      folderAbsolute.c_str(),
      COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW);
  wv3->Release();
  static_mapped_ = SUCCEEDED(hr);
  return static_mapped_;
}

bool WebViewHost::MapBehaviorData(const std::wstring& folderAbsolute) {
  if (!webview_ || folderAbsolute.empty()) {
    return false;
  }
  ICoreWebView2_3* wv3 = nullptr;
  if (FAILED(webview_->QueryInterface(IID_ICoreWebView2_3, reinterpret_cast<void**>(&wv3))) ||
      !wv3) {
    return false;
  }
  const HRESULT hr = wv3->SetVirtualHostNameToFolderMapping(
      L"calt-data.app",
      folderAbsolute.c_str(),
      COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_ALLOW);
  wv3->Release();
  behavior_mapped_ = SUCCEEDED(hr);
  return behavior_mapped_;
}

void WebViewHost::Resize() {
  if (!controller_ || !parent_) {
    return;
  }
  RECT rc{};
  GetClientRect(parent_, &rc);
  controller_->put_Bounds(rc);
}

void WebViewHost::Navigate(const std::wstring& url) {
  if (!webview_) {
    return;
  }
  webview_->Navigate(url.c_str());
}

void WebViewHost::Show(bool show) {
  if (!controller_) {
    return;
  }
  controller_->put_IsVisible(show ? TRUE : FALSE);
}
