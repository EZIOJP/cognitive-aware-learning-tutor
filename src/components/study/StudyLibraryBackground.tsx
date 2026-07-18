/** Soft theme-aware wash behind Study Library (no neon WebGL). */
export function StudyLibraryBackground() {
  return (
    <div
      className="absolute inset-0 pointer-events-none overflow-hidden"
      aria-hidden
    >
      <div className="absolute inset-0 bg-background" />
      <div
        className="absolute -top-24 -right-16 h-72 w-72 rounded-full blur-3xl opacity-40"
        style={{ background: "color-mix(in srgb, var(--primary) 22%, transparent)" }}
      />
      <div
        className="absolute -bottom-28 -left-20 h-80 w-80 rounded-full blur-3xl opacity-30"
        style={{ background: "color-mix(in srgb, var(--accent) 45%, transparent)" }}
      />
    </div>
  );
}
