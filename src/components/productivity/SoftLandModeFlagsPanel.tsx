import { useCallback, useEffect, useState } from "react";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";

type ModeKey = "study" | "free";
type LiveFlag = "block_watch_sites" | "block_porn";

type Flags = {
  block_watch_sites: boolean;
  block_porn: boolean;
  block_social: boolean;
  block_keywords: boolean;
  block_other: boolean;
  strict_allowlist: boolean;
};

const LIVE: { key: LiveFlag; label: string; consequence: string }[] = [
  {
    key: "block_watch_sites",
    label: "Block watch sites",
    consequence: "YouTube / Reddit / watch_extra + built-ins — study only; free/reward opens them",
  },
  {
    key: "block_porn",
    label: "Porn heuristic",
    consequence: "Host ladder porn filter (Allow can override). Hosts-file device lock is separate",
  },
];

const DEFAULTS: Record<ModeKey, Flags> = {
  study: {
    block_watch_sites: true,
    block_porn: true,
    block_social: true,
    block_keywords: true,
    block_other: true,
    strict_allowlist: true,
  },
  free: {
    block_watch_sites: false,
    block_porn: true,
    block_social: false,
    block_keywords: true,
    block_other: false,
    strict_allowlist: false,
  },
};

function mergeFlags(raw: Partial<Flags> | undefined, mode: ModeKey): Flags {
  return { ...DEFAULTS[mode], ...(raw || {}) };
}

/**
 * SoftLand mode_flags that SoftLand decide actually uses.
 * Dead flags stay visible but disabled so users don't think they work.
 */
export function SoftLandModeFlagsPanel() {
  const [study, setStudy] = useState<Flags>(DEFAULTS.study);
  const [free, setFree] = useState<Flags>(DEFAULTS.free);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
      if (!r.ok) throw new Error(`softland_policy.json ${r.status}`);
      const j = (await r.json()) as { mode_flags?: { study?: Partial<Flags>; free?: Partial<Flags> } };
      setStudy(mergeFlags(j.mode_flags?.study, "study"));
      setFree(mergeFlags(j.mode_flags?.free, "free"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load mode flags");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    if (!isFocusDesktopShell() || !isFocusEnforcerBridgeAvailable()) {
      setError("Mode flags need calt_focus + running enforcer");
      return;
    }
    setSaving(true);
    setError(null);
    setHint(null);
    try {
      const mode_flags = {
        study: { ...study },
        free: { ...free },
      };
      const res = await enforcerNativeCmd("softland.patch_mode_flags", { mode_flags }, 6000);
      if (!res || res.ok === false || res.error) {
        throw new Error(String(res?.error || "patch_mode_flags failed"));
      }
      invalidateFocusStatusBus({ pipe: true });
      setHint("Mode flags saved");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function toggle(mode: ModeKey, key: LiveFlag) {
    if (mode === "study") setStudy((f) => ({ ...f, [key]: !f[key] }));
    else setFree((f) => ({ ...f, [key]: !f[key] }));
  }

  if (loading) {
    return <p className="text-[11px] text-muted-foreground">Loading mode flags…</p>;
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-border/40">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border/40 text-left text-muted-foreground">
              <th className="px-3 py-2 font-medium">Rule</th>
              <th className="px-3 py-2 font-medium">Study</th>
              <th className="px-3 py-2 font-medium">Free</th>
            </tr>
          </thead>
          <tbody>
            {LIVE.map(({ key, label }) => (
              <tr key={key} className="border-b border-border/30 last:border-0">
                <td className="px-3 py-2.5 text-foreground/90">{label}</td>
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    aria-label={`${label} in study`}
                    checked={Boolean(study[key])}
                    onChange={() => toggle("study", key)}
                  />
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    aria-label={`${label} in free`}
                    checked={Boolean(free[key])}
                    onChange={() => toggle("free", key)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      {hint ? <p className="text-xs text-emerald-300">{hint}</p> : null}
      <button
        type="button"
        disabled={saving}
        onClick={() => void save()}
        className="min-h-11 rounded-lg border border-[#0B6B63] bg-[#0B6B63] px-4 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save mode flags"}
      </button>
    </div>
  );
}

export default SoftLandModeFlagsPanel;
