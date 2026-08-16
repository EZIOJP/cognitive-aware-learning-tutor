import { useCallback, useEffect, useState } from "react";
import { SectionBlockToolbar } from "./SectionBlockToolbar";
import { isBrokenBlockContent } from "./noteBlockUtils";

export type SectionBlockHandlers = {
  blockIndex: number;
  language: string;
  allowSectionEdit?: boolean;
  llmReachable?: boolean;
  onBlockSave?: (
    blockIndex: number,
    language: string,
    content: string,
    opts?: { previousContent?: string },
  ) => Promise<void>;
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
      await handlers.onBlockSave(handlers.blockIndex, handlers.language, draft, {
        previousContent: initialContent,
      });
      setEditing(false);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Could not save block");
    } finally {
      setSaving(false);
    }
  }, [draft, handlers, initialContent]);

  const onRegenerate = useCallback(async () => {
    if (!handlers?.onBlockRegenerate) return;
    if (handlers.llmReachable === false) {
      setLocalError("LLM offline — start LM Studio or set a Gemini API key.");
      return;
    }
    setLocalError(null);
    const mode = editing ? (options?.regenerateModeWhenEditing ?? "polish") : "fix";
    const source = editing ? draft : initialContent;
    const errorHint =
      renderError ||
      (isBrokenBlockContent(source) ? "Block content is empty or invalid" : undefined);

    try {
      const fixed = await handlers.onBlockRegenerate(
        handlers.blockIndex,
        handlers.language,
        source,
        errorHint,
        { mode },
      );
      setDraft(fixed);
      if (regenerateAutoSave && handlers.onBlockSave) {
        await handlers.onBlockSave(handlers.blockIndex, handlers.language, fixed, {
          previousContent: source,
        });
        setEditing(false);
      } else {
        setEditing(true);
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Regeneration failed");
    }
  }, [
    draft,
    editing,
    handlers,
    options?.regenerateModeWhenEditing,
    regenerateAutoSave,
    renderError,
    initialContent,
  ]);

  const toolbar =
    handlers?.allowSectionEdit && handlers.onBlockSave ? (
      <SectionBlockToolbar
        editing={editing}
        saving={saving}
        regenerating={regenerating}
        llmReachable={handlers.llmReachable !== false}
        showSyntaxFix={false}
        onEdit={onEdit}
        onCancel={onCancel}
        onSave={() => void onSave()}
        onRegenerate={() => void onRegenerate()}
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
