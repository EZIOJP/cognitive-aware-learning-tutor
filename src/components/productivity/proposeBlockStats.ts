/** Classify Build/propose preview blocks for status hints (including saved calendar). */

export type ProposeStatKind = "study" | "break" | "routine" | "other";

export function proposeBlockStatKind(b: {
  source?: string | null;
  category?: string | null;
  title?: string | null;
}): ProposeStatKind {
  const src = (b.source || "").toLowerCase();
  if (src === "study") return "study";
  if (src === "break") return "break";
  if (src === "routine") return "routine";

  const cat = (b.category || "").toLowerCase();
  if (["study", "reading", "lecture", "review", "work", "coding", "focus"].includes(cat)) {
    return "study";
  }
  if (cat === "break") return "break";
  if (["food", "personal", "spiritual"].includes(cat)) return "routine";

  const title = (b.title || "").toLowerCase();
  if (/\bbreak\b/.test(title)) return "break";
  if (/\b(breakfast|lunch|dinner|bath|meal|self-care|bible)\b/.test(title)) return "routine";
  // Saved focus blocks often land as source=existing with study category
  if (src === "existing" && (cat === "" || cat === "default" || cat === "study")) return "study";
  return "other";
}

export function blockDurationMinutes(b: { start_at: string; end_at: string }): number {
  return Math.max(
    0,
    Math.round((new Date(b.end_at).getTime() - new Date(b.start_at).getTime()) / 60_000),
  );
}
