/**
 * OpenJarvis desktop launcher + companion to Focus's LLM brain (`jarvis serve` :8000).
 * SoftLand / Arm / Gate stay on native C++ — only chat / Suggest use the API host.
 */

export const OPENJARVIS_DOCS = "https://open-jarvis.github.io/OpenJarvis/";
export const OPENJARVIS_GITHUB = "https://github.com/open-jarvis/OpenJarvis";

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

/** Ask calt_focus shell to launch the installed OpenJarvis desktop app. */
export function launchOpenJarvisDesktop(): boolean {
  if (!hasWebViewBridge()) return false;
  const w = window as Window & {
    chrome: { webview: { postMessage: (m: unknown) => void } };
  };
  w.chrome.webview.postMessage({
    type: "focus_shell",
    v: 1,
    action: "open_openjarvis",
  });
  return true;
}
