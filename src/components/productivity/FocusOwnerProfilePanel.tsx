import { useEffect, useState } from "react";
import { Check, CircleUserRound, Loader2 } from "lucide-react";
import {
  emptyFocusOwnerProfile,
  loadFocusOwnerProfile,
  saveFocusOwnerProfile,
  type FocusOwnerProfile,
} from "../../lib/focusOwnerProfile";
import { cn } from "../../app/components/ui/utils";

/**
 * Settings → Profile — store owner identity on this PC (Focus-local, no Study API).
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
    });
    setMsg("Cleared.");
  };

  const fieldClass =
    "mt-1.5 w-full rounded-xl border border-border/60 bg-background/60 px-3 py-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-primary/40 focus:ring-2 focus:ring-primary/20";

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-border/50 bg-foreground/[0.04]">
          <CircleUserRound className="h-5 w-5 text-foreground/80" aria-hidden />
        </div>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold tracking-tight text-foreground">
            {form.display_name.trim() || "Owner"}
          </p>
          <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
            Stored on this machine only — used in the sidebar and reports. Not synced to Study
            cloud.
          </p>
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
