import { useCallback, useEffect, useState } from "react";
import { SectionBlockToolbar } from "./SectionBlockToolbar";
import { sanitizeMermaidSource } from "./mermaidSanitize";
import { isBrokenBlockContent } from "./noteBlockUtils";

export type SectionBlockHandlers = {
  blockIndex: number;
  language: string;
  allowSectionEdit?: boolean;
  llmReachable?: boolean;
  onBlockSave?: (blockIndex: number, language: string, content: string) => Promise<void>;
  onBlockRegenerate?: (
    blockIndex: number,
    language: string,
    content: string,
    error?: string,
    opts?: { mode?: "fix" | "polish" },
  ) => Promise<string>;
  regeneratingBlock?: number | null;
};

export type SectionBlockEditOptions = {
  regenerateAutoSave?: boolean;
  regenerateLabel?: string;
  regenerateEditLabel?: string;
  regenerateModeWhenEditing?: "fix" | "polish";
};

export function useSectionBlockEdit(
  initialContent: string,
  handlers: SectionBlockHandlers | undefined,
  renderError?: string | null,
  options?: SectionBlockEditOptions,
) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(initialContent);
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const regenerateAutoSave = options?.regenerateAutoSave ?? true;

  useEffect(() => {
    if (!editing) setDraft(initialContent);
  }, [initialContent, editing]);

  const regenerating =
    handlers != null && handlers.regeneratingBlock === handlers.blockIndex;

  const onEdit = useCallback(() => {
    setDraft(initialContent);
    setEditing(true);
  }, [initialContent]);

  const onCancel = useCallback(() => {
    setDraft(initialContent);
    setEditing(false);
    setLocalError(null);
  }, [initialContent]);

  const onSave = useCallback(async () => {
    if (!handlers?.onBlockSave) return;
    setSaving(true);
    setLocalError(null);
    try {
      await handlers.onBlockSave(handlers.blockIndex, handlers.language, draft);
      setEditing(false);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Could not save block");
    } finally {
      setSaving(false);
    }
  }, [draft, handlers]);

  const onSanitizeSyntax = useCallback(async () => {
    if (handlers?.language !== "mermaid" || !handlers.onBlockSave) return;
    setSaving(true);
    setLocalError(null);
    const source = editing ? draft : initialContent;
    const fixed = sanitizeMermaidSource(source);
    try {
      await handlers.onBlockSave(handlers.blockIndex, handlers.language, fixed);
      setDraft(fixed);
      setEditing(false);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Syntax fix failed");
    } finally {
      setSaving(false);
    }
  }, [draft, editing, handlers, initialContent]);

  const onRegenerate = useCallback(async () => {
    if (!handlers?.onBlockRegenerate) return;
    if (handlers.llmReachable === false) {
      setLocalError("LLM offline — use Fix syntax or start LM Studio/Ollama (OLLAMA_ENABLED=1).");
      return;
    }
    setLocalError(null);
    const mode = editing ? (options?.regenerateModeWhenEditing ?? "polish") : "fix";
    const isMermaid = handlers.language === "mermaid";
    let source = draft;
    if (isMermaid) {
      source = sanitizeMermaidSource(draft);
    }
    const errorHint =
      renderError ||
      (isBrokenBlockContent(source) ? "Block content is empty or invalid" : undefined);

    // Local syntax fix often resolves parse errors (stadium labels, arr[i], etc.)
    if (isMermaid && renderError && source.trim() !== draft.trim()) {
      setDraft(source);
      if (regenerateAutoSave && handlers.onBlockSave) {
        try {
          await handlers.onBlockSave(handlers.blockIndex, handlers.language, source);
          setEditing(false);
          return;
        } catch (err) {
          setLocalError(err instanceof Error ? err.message : "Could not save block");
          return;
        }
      }
      return;
    }

    try {
      const fixed = await handlers.onBlockRegenerate(
        handlers.blockIndex,
        handlers.language,
        source,
        errorHint,
        { mode },
      );
      const polished = isMermaid ? sanitizeMermaidSource(fixed) : fixed;
      setDraft(polished);
      if (regenerateAutoSave && handlers.onBlockSave) {
        await handlers.onBlockSave(handlers.blockIndex, handlers.language, polished);
        setEditing(false);
      } else {
        setEditing(true);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Regeneration failed");
    }
  }, [draft, editing, handlers, options?.regenerateModeWhenEditing, regenerateAutoSave, renderError]);

  const toolbar =
    handlers?.allowSectionEdit && handlers.onBlockSave ? (
      <SectionBlockToolbar
        editing={editing}
        saving={saving}
        regenerating={regenerating}
        llmReachable={handlers.llmReachable !== false}
        showSyntaxFix={handlers.language === "mermaid"}
        onEdit={onEdit}
        onCancel={onCancel}
        onSave={() => void onSave()}
        onRegenerate={() => void onRegenerate()}
        onSanitizeSyntax={() => void onSanitizeSyntax()}
        saveDisabled={draft.trim() === initialContent.trim()}
        regenerateLabel={options?.regenerateLabel}
        regenerateEditLabel={options?.regenerateEditLabel}
      />
    ) : null;

  return {
    editing,
    draft,
    setDraft,
    toolbar,
    localError,
    displayContent: editing ? draft : initialContent,
  };
}
