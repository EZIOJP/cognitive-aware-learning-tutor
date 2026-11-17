import { useEffect, useState } from "react";
import { Check, Loader2, Shuffle } from "lucide-react";
import {
  emptyFocusOwnerProfile,
  FOCUS_AVATAR_STYLES,
  focusOwnerAvatarUrl,
  loadFocusOwnerProfile,
  saveFocusOwnerProfile,
  type FocusAvatarStyle,
  type FocusOwnerProfile,
} from "../../lib/focusOwnerProfile";
import { cn } from "../../app/components/ui/utils";

/**
 * Settings → Profile — store owner identity on this PC (Focus-local, no Study API).
 * Avatar via free DiceBear SVG CDN (no camera, no API key).
 */
export function FocusOwnerProfilePanel() {
  const [form, setForm] = useState<FocusOwnerProfile>(() => loadFocusOwnerProfile());
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setForm(loadFocusOwnerProfile());
  }, []);

  const onSave = () => {
    setSaving(true);
    setMsg(null);
    try {
      const next = saveFocusOwnerProfile({
        display_name: form.display_name.trim(),
        email: form.email.trim(),
        timezone: form.timezone.trim(),
        notes: form.notes.trim(),
        avatar_style: form.avatar_style,
        avatar_seed: form.avatar_seed.trim(),
      });
      setForm(next);
      setMsg("Saved on this PC.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const onReset = () => {
    const blank = emptyFocusOwnerProfile();
    setForm(blank);
    saveFocusOwnerProfile({
      display_name: "",
      email: "",
      timezone: blank.timezone,
      notes: "",
      avatar_style: "lorelei",
      avatar_seed: "",
    });
    setMsg("Cleared.");
  };

  const shuffleSeed = () => {
    const seed = `calt-${Math.random().toString(36).slice(2, 10)}`;
    setForm((f) => ({ ...f, avatar_seed: seed }));
  };

  const previewUrl = focusOwnerAvatarUrl(form, 160);

  const fieldClass =
    "mt-1.5 w-full rounded-xl border border-border/60 bg-background/60 px-3 py-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-primary/40 focus:ring-2 focus:ring-primary/20";

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <img
          src={previewUrl}
          alt=""
          width={44}
          height={44}
          className="h-11 w-11 shrink-0 rounded-2xl border border-border/50 bg-foreground/[0.04] object-cover"
          referrerPolicy="no-referrer"
        />
        <div className="min-w-0">
          <p className="text-[15px] font-semibold tracking-tight text-foreground">
            {form.display_name.trim() || "Owner"}
          </p>
          <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
            Stored on this machine only — used in the sidebar and reports. Avatar from free{" "}
            <span className="font-medium text-foreground/80">DiceBear</span> (no camera, no
            account).
          </p>
        </div>
      </div>

      <div>
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Avatar style
        </span>
        <div className="mt-2 flex flex-wrap gap-2">
          {FOCUS_AVATAR_STYLES.map((s) => {
            const active = form.avatar_style === s.id;
            const url = focusOwnerAvatarUrl({ ...form, avatar_style: s.id }, 72);
            return (
              <button
                key={s.id}
                type="button"
                title={s.label}
                aria-pressed={active}
                onClick={() =>
                  setForm((f) => ({ ...f, avatar_style: s.id as FocusAvatarStyle }))
                }
                className={cn(
                  "rounded-xl border p-1 transition-colors",
                  active
                    ? "border-primary/50 bg-primary/10 ring-2 ring-primary/25"
                    : "border-border/50 bg-background/40 hover:border-border hover:bg-accent/30",
                )}
              >
                <img
                  src={url}
                  alt={s.label}
                  width={40}
                  height={40}
                  className="h-10 w-10 rounded-lg"
                  referrerPolicy="no-referrer"
                />
              </button>
            );
          })}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className="flex min-w-[12rem] flex-1 flex-col">
            <span className="text-[10px] text-muted-foreground">Seed (optional)</span>
            <input
              className={cn(fieldClass, "mt-1")}
              value={form.avatar_seed}
              onChange={(e) => setForm((f) => ({ ...f, avatar_seed: e.target.value }))}
              placeholder="Leave blank to use display name"
              autoComplete="off"
            />
          </label>
          <button
            type="button"
            onClick={shuffleSeed}
            className="focus-btn-ghost mt-5 inline-flex items-center gap-1.5 px-3 text-xs"
            title="Randomize avatar seed"
          >
            <Shuffle className="h-3.5 w-3.5" />
            Shuffle
          </button>
        </div>
      </div>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Display name
        </span>
        <input
          className={fieldClass}
          value={form.display_name}
          onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
          placeholder="Your name"
          autoComplete="name"
        />
      </label>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Email
        </span>
        <input
          className={fieldClass}
          type="email"
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          placeholder="optional — for your own notes / reports"
          autoComplete="email"
        />
      </label>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Timezone
        </span>
        <input
          className={fieldClass}
          value={form.timezone}
          onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
          placeholder="e.g. Asia/Kolkata"
          autoComplete="off"
        />
      </label>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Notes
        </span>
        <textarea
          className={cn(fieldClass, "min-h-[5.5rem] resize-y")}
          value={form.notes}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          placeholder="Anything you want Focus to remember about you on this PC"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="focus-btn-primary inline-flex items-center gap-2 px-4"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          Save profile
        </button>
        <button type="button" onClick={onReset} className="focus-btn-ghost inline-flex px-4">
          Clear
        </button>
        {msg ? (
          <span className="text-[12px] text-muted-foreground" role="status">
            {msg}
            {form.updated_at ? (
              <span className="ml-1 opacity-70">
                · {new Date(form.updated_at).toLocaleString()}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
    </div>
  );
}
