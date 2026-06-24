import { Loader2, Pencil, RefreshCw, Sparkles, Wrench, X } from "lucide-react";
import { Button } from "../../app/components/ui/button";

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
  "LLM offline — start LM Studio/Ollama and set OLLAMA_ENABLED=1. Use Fix syntax for local repairs.";

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
    <div className="flex items-center gap-1 flex-wrap justify-end">
      {!editing ? (
        <>
          <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={onEdit}>
            <Pencil className="h-3 w-3 mr-1" />
            Edit
          </Button>
          {showSyntaxFix && onSanitizeSyntax && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11px] text-amber-200/90"
              disabled={regenerating || saving}
              title="Apply local Mermaid syntax fix (no AI)"
              onClick={onSanitizeSyntax}
            >
              <Wrench className="h-3 w-3 mr-1" />
              Fix syntax
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[11px] text-emerald-300"
            disabled={regenerating || !llmReachable}
            title={!llmReachable ? LLM_OFFLINE_TITLE : undefined}
            onClick={onRegenerate}
          >
            {regenerating ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <RegenIcon className="h-3 w-3 mr-1" />
            )}
            {regenLabel}
          </Button>
        </>
      ) : (
        <>
          <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-[11px]" onClick={onCancel}>
            <X className="h-3 w-3 mr-1" />
            Cancel
          </Button>
          {showSyntaxFix && onSanitizeSyntax && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-[11px] border-amber-600/40 text-amber-200"
              disabled={regenerating || saving}
              title="Apply local Mermaid syntax fix (no AI)"
              onClick={onSanitizeSyntax}
            >
              <Wrench className="h-3 w-3 mr-1" />
              Fix syntax
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 px-2 text-[11px] border-emerald-500/40 text-emerald-200"
            disabled={regenerating || !llmReachable}
            title={!llmReachable ? LLM_OFFLINE_TITLE : undefined}
            onClick={onRegenerate}
          >
            {regenerating ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3 mr-1" />
            )}
            {regenLabel}
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-7 px-2 text-[11px]"
            disabled={saveDisabled || saving}
            onClick={onSave}
          >
            {saving ? "Saving…" : "Save block"}
          </Button>
        </>
      )}
    </div>
  );
}
