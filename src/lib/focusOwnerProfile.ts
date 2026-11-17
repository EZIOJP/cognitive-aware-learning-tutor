/**
 * Local owner profile for Focus (no Study :8000).
 * Persists in WebView2 / browser localStorage under one key.
 * Avatar: free DiceBear SVG (https://www.dicebear.com) — no API key, seed from name.
 */

export type FocusAvatarStyle =
  | "lorelei"
  | "notionists"
  | "avataaars"
  | "bottts"
  | "shapes"
  | "initials";

export const FOCUS_AVATAR_STYLES: { id: FocusAvatarStyle; label: string }[] = [
  { id: "lorelei", label: "Lorelei" },
  { id: "notionists", label: "Notionists" },
  { id: "avataaars", label: "Avataaars" },
  { id: "bottts", label: "Bottts" },
  { id: "shapes", label: "Shapes" },
  { id: "initials", label: "Initials" },
];

export type FocusOwnerProfile = {
  schema_version: 1;
  display_name: string;
  email: string;
  timezone: string;
  notes: string;
  /** DiceBear style id (free CDN SVG). */
  avatar_style: FocusAvatarStyle;
  /** Optional override seed; empty → display_name / email / "calt". */
  avatar_seed: string;
  updated_at: string | null;
};

const LS_KEY = "calt.focus.owner_profile";

const STYLE_SET = new Set<string>(FOCUS_AVATAR_STYLES.map((s) => s.id));

function normalizeStyle(raw: unknown): FocusAvatarStyle {
  if (typeof raw === "string" && STYLE_SET.has(raw)) return raw as FocusAvatarStyle;
  return "lorelei";
}

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
    avatar_style: "lorelei",
    avatar_seed: "",
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
      avatar_style: normalizeStyle(j.avatar_style),
      avatar_seed: typeof j.avatar_seed === "string" ? j.avatar_seed : "",
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
  if (patch.avatar_style != null) next.avatar_style = normalizeStyle(patch.avatar_style);
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

/** Seed string for DiceBear (stable per machine owner). */
export function focusOwnerAvatarSeed(profile?: FocusOwnerProfile | null): string {
  const p = profile ?? loadFocusOwnerProfile();
  const custom = (p.avatar_seed || "").trim();
  if (custom) return custom;
  const name = (p.display_name || "").trim();
  if (name) return name;
  const email = (p.email || "").trim();
  if (email) return email;
  return "calt-focus";
}

/** Free DiceBear SVG URL — no API key. Docs: https://www.dicebear.com */
export function focusOwnerAvatarUrl(
  profile?: FocusOwnerProfile | null,
  size = 128,
): string {
  const p = profile ?? loadFocusOwnerProfile();
  const style = normalizeStyle(p.avatar_style);
  const seed = encodeURIComponent(focusOwnerAvatarSeed(p));
  const s = Math.max(32, Math.min(512, Math.round(size)));
  return `https://api.dicebear.com/9.x/${style}/svg?seed=${seed}&size=${s}`;
}
