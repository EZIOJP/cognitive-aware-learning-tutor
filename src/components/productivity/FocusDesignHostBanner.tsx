import { MonitorSmartphone } from "lucide-react";
import { isFocusDesignHost } from "../../utils/focusDataUrl";

/** Shown only on npm run dev:focus (:5174) so Cursor browser edits feel intentional. */
export function FocusDesignHostBanner() {
  if (!isFocusDesignHost()) return null;
  return (
    <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 flex items-start gap-2 text-[11px] text-sky-100/95">
      <MonitorSmartphone size={14} className="shrink-0 mt-0.5 text-sky-300" />
      <div>
        <p className="font-medium text-sky-50">Focus design host · localhost:5180</p>
        <p className="opacity-90 mt-0.5">
          Hot-reload Focus UI here. SoftLand/Arm writes need{" "}
          <code className="text-sky-50/90">calt_focus.exe</code> (enforcer pipe). Mirrors load from{" "}
          <code className="text-sky-50/90">/calt-data/</code> → <code className="text-sky-50/90">data/productivity/behavior</code>.
        </p>
      </div>
    </div>
  );
}

export default FocusDesignHostBanner;
