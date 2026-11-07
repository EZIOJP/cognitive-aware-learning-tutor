import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, FolderOpen, Loader2, RefreshCw, Upload } from "lucide-react";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import {
  focusBehaviorFile,
  focusShellAction,
  isFocusBehaviorFileAvailable,
} from "../../lib/focusBehaviorFile";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

type PendingUpdate = {
  needs_restart?: boolean;
  note?: string;
  updated_at?: string;
  [key: string]: unknown;
};

function asHostList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v) {
    const s = String(x || "")
      .trim()
      .toLowerCase()
      .replace(/^www\./, "");
    if (s && !out.includes(s)) out.push(s);
  }
  return out;
}

function extractSiteRules(raw: unknown): {
  allow_extra: string[];
  watch_extra: string[];
  block_extra: string[];
} | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const site =
    (o.site_rules as Record<string, unknown> | undefined) ||
    (o.softland as Record<string, unknown> | undefined)?.site_rules ||
    (typeof o.policy === "object" && o.policy
      ? ((o.policy as Record<string, unknown>).site_rules as Record<string, unknown> | undefined)
      : undefined) ||
    o;
  if (!site || typeof site !== "object") return null;
  const s = site as Record<string, unknown>;
  if (
    !("allow_extra" in s) &&
    !("watch_extra" in s) &&
    !("block_extra" in s) &&
    !("allow" in s)
  ) {
    return null;
  }
  return {
    allow_extra: asHostList(s.allow_extra ?? s.allow),
    watch_extra: asHostList(s.watch_extra ?? s.watch),
    block_extra: asHostList(s.block_extra ?? s.block),
  };
}

export function FocusImportUpdatePanel() {
  const focusShell = isFocusDesktopShell();
  const fileRef = useRef<HTMLInputElement>(null);
  const [importHint, setImportHint] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [updateHint, setUpdateHint] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingUpdate | null>(null);
  const [checking, setChecking] = useState(false);

  const refreshPending = useCallback(async () => {
    setChecking(true);
    setUpdateHint(null);
    try {
      const res = await fetch(`${focusDataUrl("pending_update.json")}?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        setPending(null);
        setUpdateHint("No pending update file — stack is current, or run Update UI / Update stack.");
        return;
      }
      const j = (await res.json()) as PendingUpdate;
      setPending(j);
      setUpdateHint(
        j.needs_restart
          ? "Natives staged (.new) — SoftLand off + Disarm, then Apply pending update."
          : j.note
            ? String(j.note)
            : "Pending update marker present.",
      );
    } catch {
      setPending(null);
      setUpdateHint("Could not read pending_update.json (ok if none).");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    if (focusShell) void refreshPending();
  }, [focusShell, refreshPending]);

  const onPickImport = async (file: File | null) => {
    if (!file) return;
    setImporting(true);
    setImportHint(null);
    try {
      const text = await file.text();
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error("Not valid JSON.");
      }
      const rules = extractSiteRules(parsed);
      if (!rules) {
        throw new Error(
          "No SoftLand site_rules (allow/watch/block) found. Sessions/history import is not supported yet — use Export for analysis only.",
        );
      }
      if (!isFocusEnforcerBridgeAvailable()) {
        throw new Error("Import needs Focus enforcer bridge (open calt_focus.exe).");
      }
      const res = await enforcerNativeCmd("softland.patch_site_rules", {
        allow_extra: rules.allow_extra,
        watch_extra: rules.watch_extra,
        block_extra: rules.block_extra,
      });
      if (!res || res.ok === false) {
        throw new Error(
          (res && typeof res.error === "string" && res.error) || "patch_site_rules failed",
        );
      }
      setImportHint(
        `Imported lists — allow ${rules.allow_extra.length}, watch ${rules.watch_extra.length}, block ${rules.block_extra.length}.`,
      );
    } catch (e: unknown) {
      setImportHint(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const revealExports = async () => {
    if (!isFocusBehaviorFileAvailable()) {
      setImportHint("Reveal needs Focus desktop WebView.");
      return;
    }
    const r = await focusBehaviorFile({ op: "reveal", file: "productivity_export.json" });
    setImportHint(
      r?.ok
        ? "Opened export folder in Explorer."
        : `Reveal failed (${r?.detail || r?.error || "missing"}). Export once first.`,
    );
  };

  if (!focusShell) {
    return (
      <p className="text-[11px] text-muted-foreground">
        Import + update check run inside <code className="text-[10px]">calt_focus.exe</code> (not
        the browser design host alone).
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Upload size={14} /> Import
        </h3>
        <p className="text-[11px] text-muted-foreground leading-relaxed max-w-lg">
          Restore SoftLand Allow / Watch / Block lists from a JSON backup (
          <code className="text-[10px] bg-black/30 px-1 rounded">site_rules</code> or a policy
          export). Tracking sessions stay export-only for analysis.
        </p>
        {importHint && (
          <p className="text-xs text-sky-300/95 break-words" title={importHint}>
            {importHint}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => void onPickImport(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50 disabled:opacity-50"
          >
            {importing ? <Loader2 size={13} className="animate-spin" /> : <FileUp size={13} />}
            Import SoftLand lists…
          </button>
          <button
            type="button"
            onClick={() => void revealExports()}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50"
          >
            <FolderOpen size={13} /> Reveal last export
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <RefreshCw size={14} /> Update check
        </h3>
        <p className="text-[11px] text-muted-foreground leading-relaxed max-w-lg">
          Same actions as the tray Advanced menu. Update UI refreshes the React shell; Update stack
          rebuilds/syncs; Apply pending swaps staged{" "}
          <code className="text-[10px] bg-black/30 px-1 rounded">.new</code> natives after SoftLand
          off + Disarm.
        </p>
        {updateHint && (
          <p
            className={`text-xs break-words ${pending?.needs_restart ? "text-amber-300" : "text-sky-300/95"}`}
            title={updateHint}
          >
            {updateHint}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={checking}
            onClick={() => void refreshPending()}
            className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50 disabled:opacity-50"
          >
            {checking ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Check pending
          </button>
          <button
            type="button"
            onClick={() => {
              focusShellAction("update_ui");
              setUpdateHint("Update UI started — tray balloon when done.");
              window.setTimeout(() => void refreshPending(), 4000);
            }}
            className="rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50"
          >
            Update UI
          </button>
          <button
            type="button"
            onClick={() => {
              focusShellAction("update_stack");
              setUpdateHint("Update stack started — may take several minutes.");
              window.setTimeout(() => void refreshPending(), 8000);
            }}
            className="rounded-lg border border-border/50 bg-background/35 px-3 py-2 text-xs hover:bg-accent/50"
          >
            Update stack
          </button>
          <button
            type="button"
            onClick={() => {
              focusShellAction("apply_update");
              setUpdateHint("Apply pending requested — SoftLand off + Disarm required.");
              window.setTimeout(() => void refreshPending(), 3000);
            }}
            className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 hover:bg-amber-500/20"
          >
            Apply pending update
          </button>
        </div>
      </div>
    </div>
  );
}
