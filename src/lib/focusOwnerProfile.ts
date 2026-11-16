/**
 * Local owner profile for Focus (no Study :8000).
 * Persists in WebView2 / browser localStorage under one key.
 */

export type FocusOwnerProfile = {
  schema_version: 1;
  display_name: string;
  email: string;
  timezone: string;
  notes: string;
  updated_at: string | null;
};

const LS_KEY = "calt.focus.owner_profile";

export function emptyFocusOwnerProfile(): FocusOwnerProfile {
  let tz = "";
  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    tz = "";
  }
  return {
    schema_version: 1,
    display_name: "",
    email: "",
    timezone: tz,
    notes: "",
    updated_at: null,
  };
}

export function loadFocusOwnerProfile(): FocusOwnerProfile {
  const base = emptyFocusOwnerProfile();
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return base;
    const j = JSON.parse(raw) as Partial<FocusOwnerProfile>;
    if (!j || typeof j !== "object") return base;
    return {
      schema_version: 1,
      display_name: typeof j.display_name === "string" ? j.display_name : "",
      email: typeof j.email === "string" ? j.email : "",
      timezone: typeof j.timezone === "string" && j.timezone ? j.timezone : base.timezone,
      notes: typeof j.notes === "string" ? j.notes : "",
      updated_at: typeof j.updated_at === "string" ? j.updated_at : null,
    };
  } catch {
    return base;
  }
}

export function saveFocusOwnerProfile(
  patch: Partial<Omit<FocusOwnerProfile, "schema_version" | "updated_at">>,
): FocusOwnerProfile {
  const next: FocusOwnerProfile = {
    ...loadFocusOwnerProfile(),
    ...patch,
    schema_version: 1,
    updated_at: new Date().toISOString(),
  };
  localStorage.setItem(LS_KEY, JSON.stringify(next));
  try {
    window.dispatchEvent(new CustomEvent("calt-focus-owner-profile", { detail: next }));
  } catch {
    /* ignore */
  }
  return next;
}

export function focusOwnerDisplayLabel(profile?: FocusOwnerProfile | null): string {
  const p = profile ?? loadFocusOwnerProfile();
  const name = (p.display_name || "").trim();
  return name || "This machine";
}
