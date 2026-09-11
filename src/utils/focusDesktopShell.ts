/**
 * calt_focus.exe WebView2 hosts React on calt.app / :5174 / file://.
 * When true: Productivity (blocker + calendar/plan) only — study stays in the browser.
 */
export function isFocusDesktopShell(): boolean {
  if (typeof window === "undefined") return false;
  if (window.location.protocol === "file:") return true;
  const h = window.location.hostname;
  if (h === "calt.app" || h.endsWith(".calt.app")) return true;
  // 5180 = npm run dev:focus (Vite hot-reload). 5174 = calt_focus static fallback only.
  if (
    (h === "127.0.0.1" || h === "localhost") &&
    (window.location.port === "5180" || window.location.port === "5174")
  ) {
    return true;
  }
  try {
    if (sessionStorage.getItem("calt:shell") === "focus") return true;
  } catch {
    /* ignore */
  }
  return false;
}
