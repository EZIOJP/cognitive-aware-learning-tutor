import { useState } from "react";
import { Loader2 } from "lucide-react";
import { MermaidBlockView } from "../../features/mermaid/MermaidBlockView";
import { isBrokenBlockContent } from "./noteBlockUtils";
import { useSectionBlockEdit, type SectionBlockHandlers } from "./useSectionBlockEdit";

type MermaidBlockShellProps = {
  code: string;
  sectionHandlers?: SectionBlockHandlers;
};

export function MermaidBlockShell({ code, sectionHandlers }: MermaidBlockShellProps) {
  const [renderError, setRenderError] = useState<string | null>(null);

  const handlersWithLang = sectionHandlers
    ? { ...sectionHandlers, language: "mermaid" as const }
    : undefined;

  const aiRegenerating =
    handlersWithLang != null &&
    handlersWithLang.regeneratingBlock === handlersWithLang.blockIndex;

  const { editing, draft, setDraft, toolbar, localError, displayContent } = useSectionBlockEdit(
    code,
    handlersWithLang,
    renderError,
    {
      regenerateAutoSave: true,
      regenerateLabel: "Fix with AI",
      regenerateEditLabel: "Regenerate diagram",
      regenerateModeWhenEditing: "polish",
    },
  );

  if (isBrokenBlockContent(displayContent) && !editing) {
    return (
      <div className="study-mermaid-block relative my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/20 p-3">
        <p className="text-xs text-destructive">Diagram source is missing or invalid</p>
        {toolbar && <div className="mt-2">{toolbar}</div>}
      </div>
    );
  }

  return (
    <div className="relative">
      {aiRegenerating && (
        <div
          className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-black/65 backdrop-blur-[1px] rounded-lg"
          aria-live="polite"
          aria-busy="true"
        >
          <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
          <span className="text-xs font-medium text-emerald-100">Fixing diagram with AI…</span>
        </div>
      )}
      <MermaidBlockView
        source={displayContent}
        draft={draft}
        editing={editing}
        onDraftChange={setDraft}
        paused={aiRegenerating}
        toolbar={toolbar}
        localError={localError}
        onRenderError={setRenderError}
      />
    </div>
  );
}
