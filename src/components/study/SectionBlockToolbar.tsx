import { Loader2, Pencil, RefreshCw, Sparkles, Wrench, X } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";

type SectionBlockToolbarProps = {
  editing: boolean;
  saving?: boolean;
  regenerating?: boolean;
  llmReachable?: boolean;
  showSyntaxFix?: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onRegenerate: () => void;
  onSanitizeSyntax?: () => void;
  saveDisabled?: boolean;
  regenerateLabel?: string;
  regenerateEditLabel?: string;
};

const LLM_OFFLINE_TITLE =
  "LLM offline — set OLLAMA_ENABLED=1 and LLM_API_KEY for Gemini, or start LM Studio/Ollama. Fix syntax works without AI.";

const btnBase =
  "h-8 gap-1.5 rounded-md px-2.5 text-xs font-medium shadow-none [&_svg]:size-3.5";

export function SectionBlockToolbar({
  editing,
  saving = false,
  regenerating = false,
  llmReachable = true,
  showSyntaxFix = false,
  onEdit,
  onCancel,
  onSave,
  onRegenerate,
  onSanitizeSyntax,
  saveDisabled = false,
  regenerateLabel = "Fix with AI",
  regenerateEditLabel,
}: SectionBlockToolbarProps) {
  const regenLabel = editing ? (regenerateEditLabel ?? regenerateLabel) : regenerateLabel;
  const RegenIcon = editing && regenerateEditLabel ? RefreshCw : Sparkles;

  return (
    <div className="study-section-toolbar flex items-center gap-1 flex-wrap justify-end">
      {!editing ? (
        <>
          <Button type="button" variant="ghost" size="sm" className={btnBase} onClick={onEdit}>
            <Pencil className="h-3.5 w-3.5 shrink-0" />
            Edit
          </Button>
          {showSyntaxFix && onSanitizeSyntax && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(btnBase, "text-amber-200/90 hover:text-amber-100")}
              disabled={regenerating || saving}
              title="Apply local Mermaid syntax fix (no AI)"
              onClick={onSanitizeSyntax}
            >
              <Wrench className="h-3.5 w-3.5 shrink-0" />
              Fix syntax
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(btnBase, "text-emerald-300 hover:text-emerald-200")}
            disabled={regenerating || saving || !llmReachable}
            title={!llmReachable ? LLM_OFFLINE_TITLE : undefined}
            onMouseDown={(e) => e.preventDefault()}
            onClick={onRegenerate}
          >
            {regenerating ? (
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
            ) : (
              <RegenIcon className="h-3.5 w-3.5 shrink-0" />
            )}
            {regenerating ? "Fixing…" : regenLabel}
          </Button>
        </>
      ) : (
        <>
          <Button type="button" variant="ghost" size="sm" className={btnBase} onClick={onCancel}>
            <X className="h-3.5 w-3.5 shrink-0" />
            Cancel
          </Button>
          {showSyntaxFix && onSanitizeSyntax && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn(btnBase, "border-amber-600/40 text-amber-200")}
              disabled={regenerating || saving}
              title="Apply local Mermaid syntax fix (no AI)"
              onClick={onSanitizeSyntax}
            >
              <Wrench className="h-3.5 w-3.5 shrink-0" />
              Fix syntax
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(btnBase, "border-emerald-500/40 text-emerald-200")}
            disabled={regenerating || saving || !llmReachable}
            title={!llmReachable ? LLM_OFFLINE_TITLE : undefined}
            onMouseDown={(e) => e.preventDefault()}
            onClick={onRegenerate}
          >
            {regenerating ? (
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5 shrink-0" />
            )}
            {regenerating ? "Regenerating…" : regenLabel}
          </Button>
          <Button
            type="button"
            size="sm"
            className={cn(btnBase, "bg-emerald-600 text-white hover:bg-emerald-500")}
            disabled={saveDisabled || saving}
            onClick={onSave}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </>
      )}
    </div>
  );
}
