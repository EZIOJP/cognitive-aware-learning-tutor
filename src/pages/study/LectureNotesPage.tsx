import { Link, useSearchParams } from "react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { buildStudyQuizConfig } from "../../api/globalQuizClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import {
  Database,
  BookOpen,
  ClipboardList,
  FolderOpen,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRight,
  Plus,
  ScrollText,
  Search,
  X,
} from "lucide-react";
import { generateGroundedNotes } from "../../api/corpusClient";
import {
  createLibraryFile,
  createLibraryFolder,
  deleteLibraryFile,
  deleteLibraryFolder,
  exportNoteFile,
  exportLibraryFolder,
  fetchLibraryTree,
  generateLibraryDrills,
  generateLibraryQuiz,
  pasteLibraryQuiz,
  generateNotes,
  generateNotesFromToday,
  generatePrimer,
  indexNote,
  getLlmConfig,
  getNoteContent,
  listTranscripts,
  loadLlmPrefs,
  runGapAnalysis,
  saveLlmPrefs,
  regenerateNoteBlock,
  regenerateNoteSelection,
  repairAndSaveNote,
  NoteConflictError,
  saveNoteContent,
  summarizeLibraryFolder,
  syncStudySession,
  updateLibraryFile,
  updateReadingState,
  uploadSnapshot,
  type GapAnalysisResult,
  type LibraryTree,
  type LlmConfig,
  type LlmOverrides,
  type QuizQuestion,
  type CodeDrill,
  type StudySessionItem,
  type TranscriptFile,
} from "../../api/transcriptsClient";
import { setActiveTranscript } from "../../face-tracker/activeTranscript";
import { StudyLibraryBackground } from "../../components/study/StudyLibraryBackground";
import { StudyLibraryGapPanel } from "../../components/study/StudyLibraryGapPanel";
import { StudyLibraryIntelligenceHub } from "../../components/study/StudyLibraryIntelligenceHub";
import { StudyLibraryReviewPanel } from "../../components/study/StudyLibraryReviewPanel";
import { StudyLibraryStepper, type StudyWorkflowStep } from "../../components/study/StudyLibraryStepper";
import { StudyLibraryExplorer } from "../../components/study/StudyLibraryExplorer";
import { StudyLibraryLogPanel } from "../../components/study/StudyLibraryLogPanel";
import { findLibraryFile, withPreservedScroll } from "../../components/study/studyLibraryUtils";
import {
  applyBlockUpdate,
  finalizeNoteMarkdown,
  prepareNoteMarkdown,
  sanitizeMermaidSource,
} from "../../features/study-notes";
import { extractBlockSurroundingContext, extractSelectionSurroundingContext } from "../../components/study/noteBlockUtils";
import { cn } from "../../app/components/ui/utils";
import { StudyLibraryViewer } from "../../components/study/StudyLibraryViewer";
import { StudyLibraryCreateSheet } from "../../components/study/StudyLibraryCreateSheet";
import { Button } from "../../app/components/ui/button";
import { useEaster, useKonami } from "../../easter";

type LibraryTab = "library" | "gap" | "review";

const NOTE_KINDS = [
  { value: "lecture", label: "Lecture" },
  { value: "textbook", label: "Textbook" },
  { value: "quiz", label: "Quiz" },
  { value: "exercise", label: "Exercise" },
  { value: "note", label: "Note" },
];

function folderOf(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length <= 1 ? "" : parts.slice(0, -1).join("/");
}

export function LectureNotesPage() {
  const { burst } = useEaster();
  useKonami(() => burst("doodle"));
  const [tab, setTab] = useState<LibraryTab>("library");
  const [workflowStep, setWorkflowStep] = useState<StudyWorkflowStep>(0);
  const [searchParams] = useSearchParams();
  const [createSheetOpen, setCreateSheetOpen] = useState(false);
  const [studyToolsOpen, setStudyToolsOpen] = useState(false);

  const [transcripts, setTranscripts] = useState<TranscriptFile[]>([]);
  const [libraryTree, setLibraryTree] = useState<LibraryTree | null>(null);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [selectedNote, setSelectedNote] = useState("");
  const [comparePaths, setComparePaths] = useState<string[]>([]);
  const [selectedTranscript, setSelectedTranscript] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [summarizingFolder, setSummarizingFolder] = useState("");
  const [libraryViewMode, setLibraryViewMode] = useState<"grid" | "list">("list");
  const [fileManagerCollapsed, setFileManagerCollapsed] = useState(() => {
    try {
      return localStorage.getItem("lecture-notes:file-manager-collapsed") === "1";
    } catch {
      return false;
    }
  });
  const [readingOverrides, setReadingOverrides] = useState<
    Record<string, { read_scroll_top?: number; bookmark_scroll_top?: number | null }>
  >({});
  const [openScrollTop, setOpenScrollTop] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const activeNoteRef = useRef("");
  const [newFileKind, setNewFileKind] = useState("note");
  const [content, setContent] = useState("");
  const [noteMtime, setNoteMtime] = useState<number | null>(null);
  const [compareContents, setCompareContents] = useState<[string, string]>(["", ""]);
  const [gapAnalysis, setGapAnalysis] = useState<GapAnalysisResult | null>(null);
  const [gapLoading, setGapLoading] = useState(false);
  const [intelGenerating, setIntelGenerating] = useState(false);
  const [intelStatus, setIntelStatus] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [sessionItems, setSessionItems] = useState<StudySessionItem[]>([]);
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [quizCount, setQuizCount] = useState(12);
  const [quizFocus, setQuizFocus] = useState<"mixed" | "concept" | "coding" | "cover_all">("mixed");
  const [drills, setDrills] = useState<CodeDrill[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<{
    domain: "study" | "code";
    config: Record<string, unknown>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [groundingBanner, setGroundingBanner] = useState<{
    status: string;
    reason?: string | null;
  } | null>(null);
  const [snapshotting, setSnapshotting] = useState(false);
  const [notesSemantic, setNotesSemantic] = useState(false);
  const [notesFast, setNotesFast] = useState(true);
  const [includeDiagrams, setIncludeDiagrams] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmTier, setLlmTier] = useState(
    () => loadLlmPrefs().llm_tier ?? "medium",
  );
  const [regeneratingBlock, setRegeneratingBlock] = useState<number | null>(null);

  const llmOverrides: LlmOverrides = {
    llm_tier: llmTier,
  };

  const isHeavyBudgetError = (e: unknown) =>
    e instanceof Error && e.message.includes("heavy_budget_exceeded");

  /** Run an LLM action; on heavy-budget rejection ask the user, then retry with confirmation. */
  const runWithBudgetConfirm = async <T,>(run: (llm: LlmOverrides) => Promise<T>): Promise<T> => {
    try {
      return await run(llmOverrides);
    } catch (e) {
      if (!isHeavyBudgetError(e)) throw e;
      const ok = window.confirm(
        "Daily heavy-tier cloud budget reached.\n\nContinue anyway with cloud calls for this job?",
      );
      if (!ok) throw new Error("Heavy-tier job cancelled (daily budget reached).");
      return run({ ...llmOverrides, confirm_heavy_budget: true });
    }
  };

  /** After a job, report if the gateway fell back to another provider in the chain. */
  const fallbackNotice = async (): Promise<string> => {
    try {
      const cfg = await getLlmConfig();
      const last = cfg.last_call as { fallback?: boolean; provider?: string } | null | undefined;
      if (last?.fallback && last.provider) return ` · fell back to ${last.provider}`;
    } catch {
      /* best-effort */
    }
    return "";
  };

  const compareMode = comparePaths.length >= 2;
  const showCompare = compareMode && (tab === "gap" || tab === "review");

  useEffect(() => {
    saveLlmPrefs(llmOverrides);
  }, [llmTier]);

  useEffect(() => {
    try {
      localStorage.setItem("lecture-notes:file-manager-collapsed", fileManagerCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [fileManagerCollapsed]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, tree, llm] = await Promise.all([
        listTranscripts(),
        fetchLibraryTree(),
        getLlmConfig().catch(() => null),
      ]);
      setTranscripts(t);
      setLibraryTree(tree);
      setLlmConfig(llm);
      setSelectedTranscript((prev) => prev || t[0]?.filename || "");
      const firstFile =
        tree.root.files[0] ??
        tree.root.folders.flatMap(function pick(n): typeof tree.root.files {
          return [...n.files, ...n.folders.flatMap(pick)];
        })[0];
      if (!selectedNote && firstFile) {
        setSelectedNote(firstFile.relative_path);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedTranscript) setActiveTranscript(selectedTranscript);
  }, [selectedTranscript]);

  useEffect(() => {
    const file = searchParams.get("file")?.trim();
    if (file) setSelectedNote(file);
  }, [searchParams]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const llm = await getLlmConfig(llmOverrides);
        if (!cancelled) setLlmConfig(llm);
      } catch {
        /* keep prior config */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [llmTier]);

  useEffect(() => {
    if (!selectedNote || showCompare) return;
    const meta = findLibraryFile(libraryTree, selectedNote);
    const top =
      readingOverrides[selectedNote]?.read_scroll_top ?? meta?.read_scroll_top ?? 0;
    setOpenScrollTop(top);
  }, [selectedNote, showCompare, libraryTree]);

  useEffect(() => {
    if (!selectedNote || showCompare) return;
    void (async () => {
      setContentLoading(true);
      try {
        const { content: text, mtime } = await getNoteContent(selectedNote);
        setContent(text);
        setNoteMtime(mtime ?? null);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load note");
      } finally {
        setContentLoading(false);
      }
    })();
  }, [selectedNote, showCompare]);

  useEffect(() => {
    if (!showCompare || comparePaths.length < 2) {
      setCompareContents(["", ""]);
      return;
    }
    void (async () => {
      setContentLoading(true);
      try {
        const [a, b] = await Promise.all([
          getNoteContent(comparePaths[0]),
          getNoteContent(comparePaths[1]),
        ]);
        setCompareContents([a.content, b.content]);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load compare view");
      } finally {
        setContentLoading(false);
      }
    })();
  }, [comparePaths, showCompare]);

  useEffect(() => {
    if (comparePaths.length < 2) {
      setGapAnalysis(null);
      return;
    }
    if (tab !== "gap" && tab !== "review") return;

    void (async () => {
      setGapLoading(true);
      try {
        const result = await runWithBudgetConfirm((llm) =>
          runGapAnalysis(comparePaths[0], comparePaths[1], llm),
        );
        setGapAnalysis(result);
        if (result.summary_markdown) {
          setSessionItems((prev) => {
            const without = prev.filter((i) => i.id !== "gap-summary");
            return [
              ...without,
              {
                id: "gap-summary",
                kind: "note",
                title: "Gap Analysis Summary",
                content: result.summary_markdown!,
                detail: `${result.gaps.length} gaps found`,
                approved: true,
              },
            ];
          });
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Gap analysis failed");
      } finally {
        setGapLoading(false);
      }
    })();
  }, [comparePaths, tab, llmTier]);

  useEffect(() => {
    if (comparePaths.length >= 2) setWorkflowStep(1);
    if (tab === "review") setWorkflowStep(2);
    if (tab === "library" && comparePaths.length < 2) setWorkflowStep(0);
  }, [comparePaths.length, tab]);

  useEffect(() => {
    if (comparePaths.length < 2 && tab !== "library") setTab("library");
  }, [comparePaths.length, tab]);

  const handleToggleCompare = (path: string) => {
    setComparePaths((prev) => {
      if (prev.includes(path)) return prev.filter((p) => p !== path);
      if (prev.length >= 2) return [prev[1], path];
      return [...prev, path];
    });
  };

  const folderForSave = selectedFolder;

  const handleCreateFolder = async () => {
    const name = window.prompt("New folder name", "")?.trim();
    if (!name) return;
    const path = selectedFolder ? `${selectedFolder}/${name}` : name;
    try {
      await createLibraryFolder(path);
      await refresh();
      setSelectedFolder(path);
      setToast(`Folder “${path}” created`);
      setTimeout(() => setToast(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create folder");
    }
  };

  const handleMoveFile = async (path: string, destFolder: string) => {
    if (destFolder === folderOf(path)) return;
    try {
      const row = await updateLibraryFile(path, { dest_folder: destFolder });
      await refresh();
      setSelectedNote(row.relative_path ?? row.filename);
      setToast(`Moved to ${destFolder || "library root"}`);
      setTimeout(() => setToast(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not move file");
    }
  };

  const handleDeleteFile = async (path: string) => {
    try {
      await deleteLibraryFile(path);
      if (selectedNote === path) setSelectedNote("");
      setComparePaths((prev) => prev.filter((p) => p !== path));
      await refresh();
      setToast("File deleted");
      setTimeout(() => setToast(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete file");
    }
  };

  const handleDeleteFolder = async (folderPath: string) => {
    try {
      await deleteLibraryFolder(folderPath);
      if (selectedFolder === folderPath || selectedFolder.startsWith(`${folderPath}/`)) {
        setSelectedFolder("");
      }
      await refresh();
      setToast("Folder deleted");
      setTimeout(() => setToast(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete folder");
    }
  };

  const persistNote = useCallback(async (path: string, markdown: string) => {
    const saved = await saveNoteContent(path, markdown, {
      expectedMtime: noteMtime,
    });
    setContent(markdown);
    if (saved.mtime != null) setNoteMtime(saved.mtime);
    void indexNote(path).catch(() => undefined);
  }, [noteMtime]);

  const handleSaveNoteContent = useCallback(
    async (path: string, body: string) => {
      const finalized = finalizeNoteMarkdown(body);
      try {
        await withPreservedScroll(scrollContainerRef.current, async () => {
          await persistNote(path, finalized);
        });
        setToast("Note saved");
        setTimeout(() => setToast(null), 2500);
      } catch (e) {
        if (e instanceof NoteConflictError) {
          const reload = window.confirm(
            "This note changed elsewhere (another tab or process).\n\nReload the latest version? Unsaved edits in this editor will be discarded.",
          );
          if (reload) {
            try {
              const { content: text, mtime } = await getNoteContent(path);
              setContent(text);
              setNoteMtime(mtime ?? null);
              setToast("Reloaded latest note — re-apply your edits if needed");
              setTimeout(() => setToast(null), 3500);
              // Signal caller that save did not complete (keep editor open with new base).
              throw new NoteConflictError("reloaded", mtime);
            } catch (reloadErr) {
              if (reloadErr instanceof NoteConflictError && reloadErr.message === "reloaded") {
                throw reloadErr;
              }
              setError(
                reloadErr instanceof Error ? reloadErr.message : "Could not reload note",
              );
              throw reloadErr;
            }
          }
          setError("Save cancelled — this note changed elsewhere. Reload before saving.");
          throw e;
        }
        throw e;
      }
    },
    [persistNote],
  );

  const handleExportNote = useCallback(async (path: string, format: "pdf" | "docx") => {
    try {
      await exportNoteFile(path, format);
      setToast(`Exported ${format.toUpperCase()}`);
      setTimeout(() => setToast(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }, []);

  const handleExportFolder = useCallback(async (folderPath: string, format: "pdf" | "docx") => {
    try {
      await exportLibraryFolder(folderPath, format);
      setToast(`Folder exported as ${format.toUpperCase()}`);
      setTimeout(() => setToast(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Folder export failed");
    }
  }, []);

  const handleBlockSave = useCallback(
    async (blockIndex: number, _language: string, newBlockContent: string) => {
      if (!selectedNote) {
        throw new Error("No note selected — pick a file in the library first.");
      }
      await withPreservedScroll(scrollContainerRef.current, async () => {
        const base = prepareNoteMarkdown(content);
        const updated = applyBlockUpdate(base, blockIndex, newBlockContent, { lang: _language });
        await persistNote(selectedNote, updated);
      });
      setToast("Block saved");
      setTimeout(() => setToast(null), 2500);
    },
    [content, selectedNote, persistNote],
  );

  const handleBlockRegenerate = useCallback(
    async (
      blockIndex: number,
      language: string,
      blockContent: string,
      error?: string,
      opts?: { mode?: "fix" | "polish" },
    ) => {
      setRegeneratingBlock(blockIndex);
      try {
        const block_type = language === "mermaid" ? "mermaid" : "code";
        const result = await regenerateNoteBlock({
          block_type,
          language,
          content: blockContent,
          error,
          mode: opts?.mode ?? "fix",
          note_context: extractBlockSurroundingContext(prepareNoteMarkdown(content), blockIndex, {
            blockContent,
          }),
          llm: llmOverrides,
        });
        return result.content;
      } finally {
        setRegeneratingBlock(null);
      }
    },
    [content, llmTier],
  );

  const handleSelectionRegenerate = useCallback(
    async ({
      selection,
      start,
      end,
      noteMarkdown,
      lang: _lang,
    }: {
      selection: string;
      start: number;
      end: number;
      noteMarkdown: string;
      lang: string | null;
    }) => {
      const base = prepareNoteMarkdown(noteMarkdown);

      const normalizeMermaid = (text: string): string => {
        const mermaidFence = /```mermaid\s*\n([\s\S]*?)```/i.exec(text);
        if (mermaidFence) {
          const inner = sanitizeMermaidSource(mermaidFence[1]);
          return text.replace(mermaidFence[0], `\`\`\`mermaid\n${inner}\n\`\`\``);
        }
        if (/^(graph|flowchart)\s/im.test(text.trim())) {
          const inner = sanitizeMermaidSource(
            text.replace(/^```mermaid\s*\n/i, "").replace(/\n```\s*$/i, "").trim(),
          );
          return text.includes("```mermaid") ? `\`\`\`mermaid\n${inner}\n\`\`\`` : inner;
        }
        return text;
      };

      try {
        const result = await regenerateNoteSelection({
          selection,
          note_context: extractSelectionSurroundingContext(base, start, end),
          llm: llmOverrides,
        });
        return normalizeMermaid(result.content);
      } catch (err) {
        throw err;
      }
    },
    [llmTier],
  );

  const handleRepairAllBlocks = useCallback(async () => {
    if (!selectedNote || !content.trim()) return;
    try {
      const result = await repairAndSaveNote(selectedNote, {
        use_llm: true,
        llm: llmOverrides,
      });
      await withPreservedScroll(scrollContainerRef.current, async () => {
        setContent(result.content);
        void indexNote(selectedNote).catch(() => undefined);
      });
      const n = result.fixed_count;
      setToast(n > 0 ? `Fixed ${n} block${n === 1 ? "" : "s"} with AI` : "No broken blocks found");
      setTimeout(() => setToast(null), 4000);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not repair blocks");
      throw e;
    }
  }, [content, selectedNote, llmTier]);

  const handleRepairSyntaxOnly = useCallback(async () => {
    if (!selectedNote || !content.trim()) return;
    try {
      const result = await repairAndSaveNote(selectedNote, { use_llm: false });
      await withPreservedScroll(scrollContainerRef.current, async () => {
        setContent(result.content);
        void indexNote(selectedNote).catch(() => undefined);
      });
      const n = result.fixed_count;
      setToast(n > 0 ? `Syntax-fixed ${n} block${n === 1 ? "" : "s"} (no AI)` : "No syntax fixes needed");
      setTimeout(() => setToast(null), 4000);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Syntax repair failed");
      throw e;
    }
  }, [content, selectedNote]);

  const handleSummarizeFolder = async (folderPath: string) => {
    setSummarizingFolder(folderPath);
    setError(null);
    try {
      const result = await runWithBudgetConfirm((llm) =>
        summarizeLibraryFolder(folderPath, undefined, llm),
      );
      await refresh();
      setSelectedFolder(folderPath);
      setSelectedNote(result.relative_path);
      setToast(`Folder summary created (${result.source_count} sources)`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Folder summarization failed");
    } finally {
      setSummarizingFolder("");
    }
  };

  const persistReadingPosition = useCallback(async (path: string, scrollTop: number) => {
    if (!path) return;
    const top = Math.max(0, Math.round(scrollTop));
    try {
      await updateReadingState(path, { read_scroll_top: top });
      setReadingOverrides((prev) => ({
        ...prev,
        [path]: { ...prev[path], read_scroll_top: top },
      }));
    } catch {
      /* best-effort */
    }
  }, []);

  useEffect(() => {
    const prev = activeNoteRef.current;
    activeNoteRef.current = selectedNote;
    if (!prev || prev === selectedNote || showCompare) return;
    const top = scrollContainerRef.current?.scrollTop ?? 0;
    void persistReadingPosition(prev, top);
  }, [selectedNote, showCompare, persistReadingPosition]);

  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState !== "hidden" || !selectedNote || showCompare) return;
      const top = scrollContainerRef.current?.scrollTop ?? 0;
      void persistReadingPosition(selectedNote, top);
    };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, [selectedNote, showCompare, persistReadingPosition]);

  const handleSetBookmark = useCallback(async (path: string, scrollTop: number) => {
    setReadingOverrides((prev) => ({
      ...prev,
      [path]: { ...prev[path], read_scroll_top: scrollTop, bookmark_scroll_top: scrollTop },
    }));
    try {
      await updateReadingState(path, {
        read_scroll_top: scrollTop,
        bookmark_scroll_top: scrollTop,
      });
      setToast("Bookmark saved");
      setTimeout(() => setToast(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save bookmark");
    }
  }, []);

  const handleCreateFile = async () => {
    const title = window.prompt("New file title", "Untitled")?.trim() || "Untitled";
    try {
      const row = await createLibraryFile(title, folderForSave, newFileKind);
      await refresh();
      setSelectedNote(row.relative_path ?? row.filename);
      setToast(`Created “${title}”`);
      setTimeout(() => setToast(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create file");
    }
  };

  const handleGenerate = async (opts?: { forceLegacy?: boolean }) => {
    if (!selectedTranscript) return;
    setGenerating(true);
    setError(null);
    const referencePaths = comparePaths.filter((p) => /\.(pdf|md|ipynb)$/i.test(p));
    try {
      const result = await runWithBudgetConfirm((llm) =>
        generateNotes(selectedTranscript, {
          title: noteTitle.trim() || undefined,
          topic: noteTitle.trim() || undefined,
          folderPath: folderForSave,
          referencePaths: referencePaths.length ? referencePaths : undefined,
          contextFolder: folderForSave || undefined,
          useSemanticGrouping: notesSemantic,
          fastMode: notesFast,
          enrichVisuals: includeDiagrams && !notesFast,
          forceLegacy: opts?.forceLegacy,
          llm,
        }),
      );
      await refresh();
      setSelectedNote(result.filename);
      void indexNote(result.filename).catch(() => undefined);
      setCreateSheetOpen(false);
      const handoff = (result as { corpus_handoff?: { transcript_chunks?: number; note_chunks?: number } })
        .corpus_handoff;
      const corpusMsg =
        handoff != null
          ? ` · corpus: ${handoff.transcript_chunks ?? 0} + ${handoff.note_chunks ?? 0} chunks`
          : "";
      const mode = result.mode;
      const modeMsg = mode ? ` · ${mode}` : "";
      const fbMsg = await fallbackNotice();
      if (result.grounding_status === "degraded") {
        setGroundingBanner({
          status: "degraded",
          reason: result.grounding_reason,
        });
      } else if (result.grounding_status === "grounded") {
        setGroundingBanner(null);
      }
      setToast(`Notes generated${modeMsg}${corpusMsg}${fbMsg}`);
      setTimeout(() => setToast(null), 5000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateGrounded = async () => {
    if (!selectedTranscript) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await runWithBudgetConfirm((llm) =>
        generateGroundedNotes({
          transcriptFile: selectedTranscript,
          title: noteTitle.trim() || undefined,
          topic: noteTitle.trim() || undefined,
          folderPath: folderForSave,
          llm,
        }),
      );
      if (!result.filename) {
        throw new Error("Grounded generation did not return a saved note path");
      }
      await refresh();
      setSelectedNote(result.filename);
      void indexNote(result.filename).catch(() => undefined);
      setCreateSheetOpen(false);
      const handoff = result.corpus_handoff;
      const corpusMsg =
        handoff != null
          ? ` · corpus: ${handoff.transcript_chunks ?? 0} + ${handoff.note_chunks ?? 0} chunks`
          : "";
      setToast(`Grounded notes (${result.mode})${corpusMsg}`);
      if ((result as { grounding_status?: string }).grounding_status === "degraded") {
        setGroundingBanner({
          status: "degraded",
          reason: (result as { grounding_reason?: string }).grounding_reason,
        });
      } else {
        setGroundingBanner(null);
      }
      setTimeout(() => setToast(null), 5000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grounded generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateToday = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await runWithBudgetConfirm((llm) =>
        generateNotesFromToday({
          title: noteTitle.trim() || undefined,
          topic: noteTitle.trim() || undefined,
          folderPath: folderForSave,
          useSemanticGrouping: notesSemantic,
          fastMode: notesFast,
          enrichVisuals: includeDiagrams && !notesFast,
          llm,
        }),
      );
      await refresh();
      setSelectedNote(result.filename);
      void indexNote(result.filename).catch(() => undefined);
      setCreateSheetOpen(false);
      const fbMsg = await fallbackNotice();
      if (result.grounding_status === "degraded") {
        setGroundingBanner({
          status: "degraded",
          reason: result.grounding_reason,
        });
      } else if (result.grounding_status === "grounded") {
        setGroundingBanner(null);
      }
      setToast(`Notes generated from today${fbMsg}`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleGeneratePrimer = async () => {
    const topic =
      noteTitle.trim() ||
      window.prompt("Primer topic (corpus outline before lecture)", selectedNote?.split("/").pop()?.replace(/\.md$/i, "") ?? "")?.trim();
    if (!topic) return;
    setIntelGenerating(true);
    setError(null);
    try {
      const result = await runWithBudgetConfirm((llm) =>
        generatePrimer(topic, { folderPath: folderForSave, llm }),
      );
      await refresh();
      setSelectedNote(result.relative_path);
      setToast(`Primer saved (${result.corpus_hits ?? 0} corpus hits)`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Primer failed");
    } finally {
      setIntelGenerating(false);
    }
  };

  const handleSnapshot = async () => {
    if (!selectedTranscript) return;
    setSnapshotting(true);
    setError(null);
    try {
      const blob = await captureMainAreaPng();
      if (!blob) throw new Error("Could not capture screen area.");
      const result = await uploadSnapshot(selectedTranscript, blob);
      setToast(`${result.marker} saved`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Snapshot failed");
    } finally {
      setSnapshotting(false);
    }
  };

  const sourcePaths =
    comparePaths.length >= 2 ? comparePaths : selectedNote ? [selectedNote] : [];

  const primaryMeta = findLibraryFile(libraryTree, comparePaths[0] ?? selectedNote);
  const secondaryMeta = findLibraryFile(libraryTree, comparePaths[1] ?? "");
  const activeFileMeta = findLibraryFile(libraryTree, selectedNote);
  const bookmarkScrollTop =
    readingOverrides[selectedNote]?.bookmark_scroll_top ?? activeFileMeta?.bookmark_scroll_top;

  const addSessionItem = (item: Omit<StudySessionItem, "approved">) => {
    setSessionItems((prev) => {
      const rest = prev.filter((p) => p.id !== item.id);
      return [...rest, { ...item, approved: true }];
    });
  };

  const handleTakeQuiz = () => {
    const notePath = selectedNote || primaryMeta?.relative_path || "";
    const hasQuiz = quizQuestions.length > 0;
    const hasDrills = drills.length > 0;
    if (!hasQuiz && !hasDrills) return;
    setActiveQuiz({
      domain: hasQuiz ? "study" : "code",
      config: buildStudyQuizConfig(
        quizQuestions,
        drills,
        notePath,
        noteTitle.trim() || primaryMeta?.title,
      ),
    });
  };

  const handleGenerateQuiz = async (): Promise<QuizQuestion[]> => {
    if (sourcePaths.length === 0) return [];
    setIntelGenerating(true);
    setIntelStatus(
      quizFocus === "cover_all"
        ? "Starting bulk cover-all (multi-call)…"
        : "Starting quiz generation…",
    );
    setError(null);
    try {
      const folderPath =
        selectedNote && selectedNote.includes("/")
          ? selectedNote.replace(/\\/g, "/").split("/").slice(0, -1).join("/")
          : folderForSave;
      if (quizFocus === "cover_all") {
        setIntelStatus("Sending section + role batches to AI…");
      } else {
        setIntelStatus("Calling AI (quiz_gen)…");
      }
      const result = await runWithBudgetConfirm((llm) =>
        generateLibraryQuiz(sourcePaths, {
          count: quizFocus === "cover_all" ? Math.max(quizCount, 20) : quizCount,
          focus: quizFocus,
          topic: noteTitle.trim() || primaryMeta?.title,
          llm,
          expandSiblings: true,
          save: quizFocus === "cover_all" ? true : undefined,
          folderPath,
        }),
      );
      setIntelStatus("Packaging draft…");
      setQuizQuestions(result.questions);
      addSessionItem(result.session_item);
      const nFiles = result.source_paths_used?.length ?? sourcePaths.length;
      const fileHint =
        nFiles > 1
          ? result.expanded
            ? ` · ${nFiles} notes (added folder siblings — primary was short)`
            : ` · ${nFiles} notes`
          : "";
      const saveHint = result.saved_path ? ` · saved ${result.saved_path}` : "";
      const coverHint =
        quizFocus === "cover_all" && result.sections_covered?.length
          ? ` · ${result.sections_covered.length} sections`
          : "";
      const callHint =
        typeof result.llm_calls === "number" && result.llm_calls > 0
          ? ` · ${result.llm_calls} AI calls`
          : "";
      const fillHint =
        typeof result.questions_from_llm === "number"
          ? result.questions_from_extractive
            ? ` · ${result.questions_from_llm} from AI + ${result.questions_from_extractive} note-facts`
            : ` · ${result.questions_from_llm} from AI`
          : "";
      if (result.source === "extractive" || result.source === "template") {
        setToast(
          `Quiz draft from note facts (LLM offline / failed)${fileHint}${callHint} — check AI in Settings; bulk needs a working model`,
        );
      } else if (result.source === "mixed") {
        setToast(
          `Partial AI quiz: ${result.questions.length} Qs${fillHint}${coverHint}${saveHint} — review carefully`,
        );
        if (result.saved) void refresh();
      } else if (quizFocus === "cover_all") {
        setToast(
          `Bulk quiz ready: ${result.questions.length} Qs${callHint}${fillHint}${coverHint}${saveHint} — review, then Take quiz`,
        );
        if (result.saved) void refresh();
      } else {
        setToast(
          `Quiz draft ready (${result.source ?? "ok"})${callHint}${fileHint} — review, then Take quiz`,
        );
      }
      setTimeout(() => setToast(null), 5500);
      return result.questions;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Quiz generation failed");
      return [];
    } finally {
      setIntelGenerating(false);
      setIntelStatus(null);
    }
  };

  const handlePasteQuiz = async (text: string) => {
    setIntelGenerating(true);
    setError(null);
    try {
      const result = await pasteLibraryQuiz(text, {
        topic: noteTitle.trim() || primaryMeta?.title,
      });
      setQuizQuestions(result.questions);
      addSessionItem(result.session_item);
      setToast(`Imported ${result.questions.length} questions into draft — review, then Take quiz`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Paste import failed");
    } finally {
      setIntelGenerating(false);
    }
  };

  const handleTestKnowledge = async () => {
    if (sourcePaths.length === 0) {
      setError("Select a lecture note in the library first.");
      return;
    }
    // Generate fills draft only — do not auto-start the quiz runner.
    if (quizQuestions.length === 0) {
      await handleGenerateQuiz();
      return;
    }
    const notePath = selectedNote || primaryMeta?.relative_path || "";
    setActiveQuiz({
      domain: "study",
      config: buildStudyQuizConfig(
        quizQuestions,
        drills,
        notePath,
        noteTitle.trim() || primaryMeta?.title,
      ),
    });
  };

  const handleGenerateDrills = async () => {
    if (sourcePaths.length === 0) return;
    setIntelGenerating(true);
    setIntelStatus("Calling AI for code drills…");
    setError(null);
    try {
      const result = await runWithBudgetConfirm((llm) =>
        generateLibraryDrills(sourcePaths, {
          count: 2,
          topic: noteTitle.trim() || primaryMeta?.title,
          llm,
        }),
      );
      setDrills(result.drills);
      addSessionItem(result.session_item);
      setToast(`Drills generated (${result.source ?? "ok"})`);
      setTimeout(() => setToast(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Drill generation failed");
    } finally {
      setIntelGenerating(false);
      setIntelStatus(null);
    }
  };

  const handleFinalizeSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      const { count, saved } = await syncStudySession(folderForSave, sessionItems);
      await refresh();
      if (saved[0]) setSelectedNote(saved[0].relative_path);
      setSessionItems([]);
      const noteContentChanged = sessionItems.some((i) => i.approved && i.kind === "note");
      if (noteContentChanged) {
        setQuizQuestions([]);
        setDrills([]);
      }
      setGapAnalysis(null);
      setComparePaths([]);
      setTab("library");
      setToast(`Saved ${count} file${count !== 1 ? "s" : ""} to library`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const navItems: { id: LibraryTab; label: string; icon: typeof BookOpen }[] = [
    { id: "library", label: "Library", icon: BookOpen },
    ...(comparePaths.length >= 2
      ? [
          { id: "gap" as const, label: "Gap Analysis", icon: Search },
          { id: "review" as const, label: "Review & Sync", icon: ClipboardList },
        ]
      : []),
  ];

  const referenceHint = comparePaths
    .filter((p) => /\.(pdf|md|ipynb)$/i.test(p))
    .map((p) => p.split("/").pop())
    .join(", ");

  return (
    <div className="study-library-page flex flex-col min-h-0">
      <StudyLibraryBackground />

      <div className="relative z-10 flex flex-col h-full min-h-0 p-4 gap-3">
        <header className="study-library-glass flex flex-wrap items-center gap-3 px-4 py-3 shrink-0">
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-bold text-foreground tracking-wide">Study Library</h1>
            <p className="text-xs text-muted-foreground">Read, edit, and export your lecture notes</p>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="sr-only">LLM tier</span>
              <select
                value={llmTier}
                onChange={(e) => setLlmTier(e.target.value)}
                className="h-8 rounded-md border border-border bg-background/60 px-2 text-xs text-foreground"
              >
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="heavy">Heavy</option>
              </select>
            </label>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              asChild
            >
              <Link to="/knowledge-base">
                <Database className="w-3.5 h-3.5 mr-1.5" />
                Knowledge Base
              </Link>
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              onClick={() => setCreateSheetOpen(true)}
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              New from captions
            </Button>
            {tab === "library" && (
              <Button
                type="button"
                size="sm"
                variant={studyToolsOpen ? "default" : "outline"}
                className="h-8 text-xs"
                onClick={() => setStudyToolsOpen((o) => !o)}
              >
                <PanelRight className="w-3.5 h-3.5 mr-1.5" />
                Study tools
              </Button>
            )}
            <Button size="sm" variant="ghost" className="h-8 text-xs" asChild>
              <Link to="/review?tab=due&source=lecture_notes">Review Hub</Link>
            </Button>
            <Button size="sm" variant="ghost" className="h-8 text-xs" asChild>
              <Link to="/system-logs">
                <ScrollText className="w-3.5 h-3.5 mr-1" />
                Logs
              </Link>
            </Button>
          </div>

          {navItems.length > 1 && (
            <nav className="flex items-center gap-4 text-sm font-medium w-full sm:w-auto border-t sm:border-t-0 border-border pt-2 sm:pt-0">
              {navItems.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className="study-library-nav-tab flex items-center gap-1.5 pb-0.5"
                  data-active={tab === id}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}
            </nav>
          )}

          {toast && <span className="text-xs text-primary">{toast}</span>}
          {groundingBanner?.status === "degraded" ? (
            <div
              className="w-full mt-2 rounded-md border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-xs text-amber-100"
              role="status"
            >
              Generated from transcript only — textbook grounding unavailable
              {groundingBanner.reason ? ` (${groundingBanner.reason})` : ""}.
            </div>
          ) : null}
        </header>

        {(tab === "gap" || tab === "review") && (
          <StudyLibraryStepper
            step={workflowStep}
            onStepChange={(s) => {
              setWorkflowStep(s);
              if (s === 0) setTab("library");
              if (s === 1) setTab("gap");
              if (s === 2) setTab("review");
            }}
          />
        )}

        <main className="flex flex-1 gap-3 min-h-0 overflow-hidden">
          <aside
            className={cn(
              "study-library-glass study-library-sidebar shrink-0 flex flex-col min-h-0 overflow-hidden",
              fileManagerCollapsed
                ? "study-library-sidebar--collapsed"
                : "study-library-sidebar--expanded",
            )}
          >
            {fileManagerCollapsed ? (
              <div className="study-library-sidebar-rail">
                <button
                  type="button"
                  className="study-library-sidebar-rail-btn"
                  onClick={() => setFileManagerCollapsed(false)}
                  title="Expand file manager"
                  aria-label="Expand file manager"
                >
                  <PanelLeftOpen className="w-4 h-4" />
                </button>
                <div className="study-library-sidebar-rail-icon" title="Library">
                  <FolderOpen className="w-4 h-4" />
                </div>
                {selectedNote ? (
                  <span className="study-library-sidebar-rail-note" title={selectedNote}>
                    {selectedNote.split("/").pop()}
                  </span>
                ) : null}
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-hidden">
                {loading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  </div>
                ) : error && !libraryTree ? (
                  <p className="text-xs text-red-400 p-3">{error}</p>
                ) : libraryTree ? (
                  <StudyLibraryExplorer
                    tree={libraryTree}
                    browsePath={selectedFolder}
                    selectedFile={selectedNote}
                    comparePaths={comparePaths}
                    onBrowsePath={setSelectedFolder}
                    onSelectFile={setSelectedNote}
                    onToggleCompare={handleToggleCompare}
                    onMoveFile={(path, dest) => void handleMoveFile(path, dest)}
                    onDeleteFile={(path) => void handleDeleteFile(path)}
                    onDeleteFolder={(path) => void handleDeleteFolder(path)}
                    onSummarizeFolder={(path) => void handleSummarizeFolder(path)}
                    onNewFolder={() => void handleCreateFolder()}
                    onNewFile={() => void handleCreateFile()}
                    viewMode={libraryViewMode}
                    onViewModeChange={setLibraryViewMode}
                    summarizingFolder={summarizingFolder}
                    onCollapse={() => setFileManagerCollapsed(true)}
                  />
                ) : null}
              </div>
            )}
          </aside>

          <div className="flex-1 flex flex-col min-w-0 min-h-0 gap-2">
            {error && !loading && (
              <p className="text-xs text-red-400 shrink-0 px-1">{error}</p>
            )}

            {comparePaths.length > 0 && tab === "library" && (
              <div className="study-library-compare-bar shrink-0">
                <span className="text-xs text-muted-foreground truncate">
                  Compare: {comparePaths.map((p) => p.split("/").pop()).join(" · ")}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs shrink-0"
                  onClick={() => setComparePaths([])}
                >
                  <X className="w-3.5 h-3.5 mr-1" />
                  Clear
                </Button>
                {comparePaths.length >= 2 && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs shrink-0"
                    onClick={() => setTab("gap")}
                  >
                    Open gap analysis
                  </Button>
                )}
              </div>
            )}

            {(tab === "gap" || tab === "review") && comparePaths.length >= 2 && (
              <StudyLibraryGapPanel gap={gapAnalysis} loading={gapLoading} />
            )}

            <StudyLibraryViewer
              mode={showCompare ? "compare" : "single"}
              showSyncHeader={showCompare}
              loading={contentLoading}
              primaryTitle={primaryMeta?.title ?? "Lecture notes"}
              secondaryTitle={secondaryMeta?.title ?? "Reference"}
              primaryContent={showCompare ? compareContents[0] : content}
              secondaryContent={showCompare ? compareContents[1] : undefined}
              relativePath={!showCompare ? selectedNote : undefined}
              initialScrollTop={openScrollTop}
              bookmarkScrollTop={bookmarkScrollTop}
              editable={!showCompare && Boolean(selectedNote)}
              onSaveContent={handleSaveNoteContent}
              snapshotTranscript={selectedTranscript || undefined}
              onExport={handleExportNote}
              onExportFolder={handleExportFolder}
              exportFolderPath={folderForSave}
              onTakeQuiz={!showCompare && selectedNote ? () => void handleTestKnowledge() : undefined}
              quizReady={quizQuestions.length > 0}
              quizLoading={intelGenerating}
              quizDisabled={false}
              onScrollContainer={(el) => {
                scrollContainerRef.current = el;
              }}
              onSetBookmark={(path, top) => void handleSetBookmark(path, top)}
              sectionEdit={
                !showCompare && selectedNote
                  ? {
                      allowSectionEdit: true,
                      llmReachable: Boolean(llmConfig?.reachable),
                      regeneratingBlock,
                      onBlockSave: handleBlockSave,
                      onBlockRegenerate: handleBlockRegenerate,
                    }
                  : undefined
              }
              llmReachable={Boolean(llmConfig?.reachable)}
              llmTier={llmTier}
              onRepairSyntaxOnly={handleRepairSyntaxOnly}
              onRepairAllBlocks={handleRepairAllBlocks}
              onRegenerateSelection={handleSelectionRegenerate}
            />
          </div>

          {tab === "review" ? (
            <StudyLibraryReviewPanel
              items={sessionItems}
              compareCount={comparePaths.length}
              syncing={syncing}
              onToggleApproved={(id) =>
                setSessionItems((prev) =>
                  prev.map((i) => (i.id === id ? { ...i, approved: !i.approved } : i)),
                )
              }
              onApproveAll={() =>
                setSessionItems((prev) => prev.map((i) => ({ ...i, approved: true })))
              }
              onFinalize={() => void handleFinalizeSync()}
            />
          ) : studyToolsOpen ? (
            <StudyLibraryIntelligenceHub
              comparePaths={comparePaths}
              selectedNotePath={selectedNote}
              compareCount={comparePaths.length}
              quizQuestions={quizQuestions}
              drills={drills}
              sessionItems={sessionItems}
              generating={intelGenerating}
              generatingDetail={intelStatus}
              quizCount={quizCount}
              quizFocus={quizFocus}
              onQuizCountChange={setQuizCount}
              onQuizFocusChange={(f) => {
                setQuizFocus(f);
                if (f === "cover_all" && quizCount < 20) setQuizCount(30);
              }}
              onGenerateQuiz={() => void handleGenerateQuiz()}
              onGenerateDrills={() => void handleGenerateDrills()}
              onPasteQuiz={(text) => void handlePasteQuiz(text)}
              onRemoveQuestion={(id) =>
                setQuizQuestions((prev) => prev.filter((q) => q.id !== id))
              }
              onGeneratePrimer={
                llmConfig?.corpus_grounded_notes ? () => void handleGeneratePrimer() : undefined
              }
              corpusGroundedNotes={Boolean(llmConfig?.corpus_grounded_notes)}
              onTakeQuiz={handleTakeQuiz}
              onEditItem={(id, content) =>
                setSessionItems((prev) =>
                  prev.map((i) => (i.id === id ? { ...i, content } : i)),
                )
              }
              onSync={() => {
                setTab("review");
                setWorkflowStep(2);
              }}
            />
          ) : null}
        </main>
      </div>

      <StudyLibraryCreateSheet
        open={createSheetOpen}
        onOpenChange={setCreateSheetOpen}
        transcripts={transcripts}
        selectedTranscript={selectedTranscript}
        onTranscriptChange={setSelectedTranscript}
        noteTitle={noteTitle}
        onNoteTitleChange={setNoteTitle}
        notesSemantic={notesSemantic}
        onNotesSemanticChange={setNotesSemantic}
        notesFast={notesFast}
        onNotesFastChange={setNotesFast}
        includeDiagrams={includeDiagrams}
        onIncludeDiagramsChange={setIncludeDiagrams}
        llmConfig={llmConfig}
        generating={generating}
        snapshotting={snapshotting}
        onGenerate={() => void handleGenerate()}
        onGenerateGrounded={
          llmConfig?.corpus_grounded_notes ? () => void handleGenerateGrounded() : undefined
        }
        onGenerateToday={() => void handleGenerateToday()}
        onSnapshot={() => void handleSnapshot()}
        referenceHint={referenceHint || undefined}
      />

      {(generating || intelGenerating) && (
        <div className="fixed bottom-4 right-4 z-40 w-[min(420px,92vw)] shadow-xl">
          <StudyLibraryLogPanel
            title="Generating — live log"
            defaultFile="notes_generation.log"
            live
            pollMs={2000}
            compact
            maxLines={120}
          />
        </div>
      )}

      {activeQuiz && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl bg-background shadow-xl">
            <GlobalQuizRunner
              domain={activeQuiz.domain}
              config={activeQuiz.config}
              navigateOnComplete={false}
              onDone={() => {
                setActiveQuiz(null);
                setToast("Quiz done — cards queued. Open Review Hub for spaced repetition.");
                setTimeout(() => setToast(null), 5000);
              }}
              onClose={() => setActiveQuiz(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
