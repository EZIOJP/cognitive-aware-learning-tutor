/**
 * Focus shell data plane: WebView2 maps calt-data.app → data/productivity/behavior.
 * Vite design host (:5180) serves the same files under /calt-data/.
 */
import { isFocusDesktopShell } from "./focusDesktopShell";

export function focusDataBaseUrl(): string {
  if (typeof window === "undefined") return "https://calt-data.app";
  const h = window.location.hostname;
  const port = window.location.port;
  if ((h === "127.0.0.1" || h === "localhost") && (port === "5180" || port === "5174")) {
    return "/calt-data";
  }
  return "https://calt-data.app";
}

export function focusDataUrl(file: string): string {
  const name = file.replace(/^\//, "");
  return `${focusDataBaseUrl()}/${name}`;
}

/** True when editing Focus UI in Cursor via npm run dev:focus. */
export function isFocusDesignHost(): boolean {
  if (typeof window === "undefined") return false;
  if (!isFocusDesktopShell()) return false;
  const port = window.location.port;
  return port === "5180";
}
