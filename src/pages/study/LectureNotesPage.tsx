import { Link, useSearchParams } from "react-router";
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { buildStudyQuizConfig } from "../../api/globalQuizClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import {
  BookOpen,
  ClipboardList,
  Loader2,
  Minimize2,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRight,
  Plus,
  ScrollText,
  Search,
  X,
} from "lucide-react";
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
  fetchNoteTopics,
  generateNotes,
  generateNotesFromToday,
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
import { StudyLibraryGapPanel } from "../../components/study/StudyLibraryGapPanel";
import { StudyLibraryIntelligenceHub } from "../../components/study/StudyLibraryIntelligenceHub";
import { StudyLibraryReviewPanel } from "../../components/study/StudyLibraryReviewPanel";
import { StudyLibraryStepper, type StudyWorkflowStep } from "../../components/study/StudyLibraryStepper";
import { StudyLibraryExplorer } from "../../components/study/StudyLibraryExplorer";
import { StudyLibraryLogPanel } from "../../components/study/StudyLibraryLogPanel";
import { findLibraryFile, isImportableNoteFile, titleFromImportFileName, withPreservedScroll } from "../../components/study/studyLibraryUtils";
import { setLectureNotesPresence } from "../../utils/lectureNotesPresence";
import {
  applyBlockUpdate,
  finalizeNoteMarkdown,
  prepareNoteMarkdown,
  sanitizeMermaidSource,
} from "../../features/study-notes";
import { extractBlockSurroundingContext, extractSelectionSurroundingContext } from "../../components/study/noteBlockUtils";
import { StudyLibraryViewer } from "../../components/study/StudyLibraryViewer";
import { StudyLibraryCreateSheet } from "../../components/study/StudyLibraryCreateSheet";
import { Button } from "../../app/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../app/components/ui/dropdown-menu";
import { useEaster, useKonami } from "../../easter";

type LibraryTab = "library" | "gap" | "review";

const NOTE_KINDS = [
  { value: "lecture", label: "Lecture" },
  { value: "textbook", label: "Textbook" },
  { value: "quiz", label: "Quiz" },
  { value: "exercise", label: "Exercise" },
  { value: "note", label: "Note" },
];

const LS_FILE_MANAGER_COLLAPSED = "lecture-notes:file-manager-collapsed";
const LS_LAST_OPEN_NOTE = "lecture-notes:last-open-path";
const LS_NOTE_FONT_STEP = "lecture-notes:font-step";
const NOTE_FONT_STEPS = [1.05, 1.2, 1.35, 1.5, 1.7, 1.9, 2.2];
const DEFAULT_NOTE_FONT_STEP = 3;

function readNoteFontStep(): number {
  try {
    const n = Number(localStorage.getItem(LS_NOTE_FONT_STEP));
    if (Number.isInteger(n) && n >= 0 && n < NOTE_FONT_STEPS.length) return n;
  } catch {
    /* ignore */
  }
  return DEFAULT_NOTE_FONT_STEP;
}

function folderOf(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length <= 1 ? "" : parts.slice(0, -1).join("/");
}

function remapLegacyNotePath(path: string): string {
  const rel = path.replace(/\\/g, "/").replace(/^\/+/, "");
  if (!rel || rel.startsWith("data_foundations/")) return rel;
  const aliases: [string, string][] = [
    ["lecture5/", "data_foundations/lecture_5/"],
    ["lecture_5/", "data_foundations/lecture_5/"],
    ["lecture_4/", "data_foundations/lecture_4/"],
    ["lecture_3/", "data_foundations/lecture_3/"],
    ["lecture_2/", "data_foundations/lecture_2/"],
  ];
  for (const [old, neu] of aliases) {
    if (rel.startsWith(old)) return neu + rel.slice(old.length);
  }
  return rel;
}

function readLastOpenNote(): string {
  try {
    const raw = localStorage.getItem(LS_LAST_OPEN_NOTE)?.trim() || "";
    return remapLegacyNotePath(raw);
  } catch {
    return "";
  }
}

function writeLastOpenNote(path: string) {
  try {
    if (path) localStorage.setItem(LS_LAST_OPEN_NOTE, path);
  } catch {
    /* ignore */
  }
}

export function LectureNotesPage() {
  const { burst } = useEaster();
  useKonami(() => burst("doodle"));
  const [tab, setTab] = useState<LibraryTab>("library");
  const [workflowStep, setWorkflowStep] = useState<StudyWorkflowStep>(0);
  const [searchParams] = useSearchParams();
  const [createSheetOpen, setCreateSheetOpen] = useState(false);
  const [studyToolsOpen, setStudyToolsOpen] = useState(false);
  const [docChromeHost, setDocChromeHost] = useState<HTMLElement | null>(null);

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
      return localStorage.getItem(LS_FILE_MANAGER_COLLAPSED) === "1";
    } catch {
      return false;
    }
  });
  const [notesFullscreen, setNotesFullscreen] = useState(false);
  const [noteFontStep, setNoteFontStep] = useState(readNoteFontStep);
  const fullscreenRootRef = useRef<HTMLDivElement | null>(null);
  const fileManagerBeforeFsRef = useRef(false);
  const [readingOverrides, setReadingOverrides] = useState<
    Record<string, { read_scroll_top?: number; bookmark_scroll_top?: number | null }>
  >({});
  const [openScrollTop, setOpenScrollTop] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const activeNoteRef = useRef("");
  /** Last user activity (scroll / focus) while a note is open — keeps reading credit fresh. */
  const lastReadActivityRef = useRef(Date.now());
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
  const [noteTopics, setNoteTopics] = useState<
    { topic_id: string; title: string; label: string; char_count?: number; source?: string }[]
  >([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
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
  const [importing, setImporting] = useState(false);
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
    if (notesFullscreen) return;
    try {
      localStorage.setItem(LS_FILE_MANAGER_COLLAPSED, fileManagerCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [fileManagerCollapsed, notesFullscreen]);

  useEffect(() => {
    try {
      localStorage.setItem(LS_NOTE_FONT_STEP, String(noteFontStep));
    } catch {
      /* ignore */
    }
  }, [noteFontStep]);

  const bumpNoteFont = useCallback((delta: -1 | 1) => {
    setNoteFontStep((prev) => Math.min(NOTE_FONT_STEPS.length - 1, Math.max(0, prev + delta)));
  }, []);

  const exitNotesFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => undefined);
    }
    setNotesFullscreen(false);
    setFileManagerCollapsed(fileManagerBeforeFsRef.current);
  }, []);

  const toggleNotesFullscreen = useCallback(() => {
    if (notesFullscreen) {
      exitNotesFullscreen();
      return;
    }
    fileManagerBeforeFsRef.current = fileManagerCollapsed;
    setFileManagerCollapsed(true);
    setStudyToolsOpen(false);
    setNotesFullscreen(true);
    const el = fullscreenRootRef.current;
    void el?.requestFullscreen?.().catch(() => undefined);
  }, [exitNotesFullscreen, fileManagerCollapsed, notesFullscreen]);

  useEffect(() => {
    if (!notesFullscreen) return;
    const onFs = () => {
      if (!document.fullscreenElement) {
        setNotesFullscreen(false);
        setFileManagerCollapsed(fileManagerBeforeFsRef.current);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") exitNotesFullscreen();
    };
    document.addEventListener("fullscreenchange", onFs);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("fullscreenchange", onFs);
      window.removeEventListener("keydown", onKey);
    };
  }, [notesFullscreen, exitNotesFullscreen]);

  useEffect(() => {
    const path = remapLegacyNotePath(selectedNote || "");
    if (!path || !path.endsWith(".md")) {
      setNoteTopics([]);
      setSelectedTopicIds([]);
      return;
    }
    let cancelled = false;
    setTopicsLoading(true);
    void fetchNoteTopics(path)
      .then((res) => {
        if (cancelled) return;
        setNoteTopics(res.topics || []);
        setSelectedTopicIds([]);
      })
      .catch(() => {
        if (!cancelled) {
          setNoteTopics([]);
          setSelectedTopicIds([]);
        }
      })
      .finally(() => {
        if (!cancelled) setTopicsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedNote]);

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
      const fromUrl = searchParams.get("file")?.trim() || "";
      const lastOpen = readLastOpenNote();
      setSelectedNote((prev) => {
        if (prev && findLibraryFile(tree, prev)) return prev;
        if (fromUrl && findLibraryFile(tree, fromUrl)) return fromUrl;
        if (lastOpen && findLibraryFile(tree, lastOpen)) return lastOpen;
        return firstFile?.relative_path ?? "";
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    if (selectedTranscript) setActiveTranscript(selectedTranscript);
  }, [selectedTranscript]);

  useEffect(() => {
    const file = searchParams.get("file")?.trim();
    if (file) setSelectedNote(file);
  }, [searchParams]);

  useEffect(() => {
    if (!selectedNote) return;
    writeLastOpenNote(selectedNote);
    setSelectedFolder((prev) => {
      const folder = folderOf(selectedNote);
      // Keep browse folder aligned when restoring last note (don't fight user browsing)
      if (!prev) return folder;
      return prev;
    });
  }, [selectedNote]);

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
        setContent("");
        setNoteMtime(null);
        // Don't sticky-banner note fetch failures (shows as noisy "Failed to fetch")
        const msg = e instanceof Error ? e.message : "Failed to load note";
        setToast(msg);
        setTimeout(() => setToast(null), 4000);
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
        const msg = e instanceof Error ? e.message : "Failed to load compare view";
        setToast(msg);
        setTimeout(() => setToast(null), 4000);
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
    async (
      blockIndex: number,
      _language: string,
      newBlockContent: string,
      opts?: { previousContent?: string },
    ) => {
      if (!selectedNote) {
        throw new Error("No note selected — pick a file in the library first.");
      }
      await withPreservedScroll(scrollContainerRef.current, async () => {
        const base = prepareNoteMarkdown(content);
        const updated = applyBlockUpdate(base, blockIndex, newBlockContent, {
          lang: _language,
          previousContent: opts?.previousContent,
        });
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

  // Publish reading signal for SPA study credit (loaded note + visible/focused + recent activity).
  useEffect(() => {
    const notesLoaded =
      Boolean(selectedNote) && !showCompare && !contentLoading && Boolean(content.trim());
    const noteTitleHint =
      findLibraryFile(libraryTree, selectedNote)?.title || selectedNote || null;

    const publish = () => {
      const visible =
        typeof document === "undefined" || document.visibilityState === "visible";
      const focused = typeof document === "undefined" || document.hasFocus();
      // Fresh open counts as reading for 2 minutes; scroll/pointer refresh the timer.
      const recent = Date.now() - lastReadActivityRef.current < 120_000;
      const reading = notesLoaded && visible && focused && recent;
      setLectureNotesPresence({
        notesLoaded,
        reading,
        documentId: selectedNote || null,
        title: noteTitleHint,
      });
    };

    if (notesLoaded) {
      lastReadActivityRef.current = Date.now();
    }
    publish();
    if (!notesLoaded) {
      return () => setLectureNotesPresence(null);
    }

    const onActivity = () => {
      lastReadActivityRef.current = Date.now();
      publish();
    };
    const onVis = () => publish();
    const id = window.setInterval(publish, 15_000);
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", onActivity);
    window.addEventListener("blur", onVis);
    const el = scrollContainerRef.current;
    el?.addEventListener("scroll", onActivity, { passive: true });
    document.addEventListener("pointerdown", onActivity, { passive: true });
    document.addEventListener("keydown", onActivity);

    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("focus", onActivity);
      window.removeEventListener("blur", onVis);
      el?.removeEventListener("scroll", onActivity);
      document.removeEventListener("pointerdown", onActivity);
      document.removeEventListener("keydown", onActivity);
      setLectureNotesPresence(null);
    };
  }, [selectedNote, showCompare, contentLoading, content, libraryTree]);

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

  const handleImportFiles = async (files: File[], destFolder: string) => {
    const candidates = files.filter(isImportableNoteFile);
    const skipped = files.length - candidates.length;
    if (!candidates.length) {
      setError("Drop .md, .markdown, or .txt note files");
      return;
    }
    setImporting(true);
    setError(null);
    let lastPath = "";
    let imported = 0;
    try {
      for (const file of candidates) {
        if (file.size > 500_000) {
          throw new Error(`“${file.name}” is too large (max 500 KB)`);
        }
        const content = await file.text();
        const title = titleFromImportFileName(file.name);
        const row = await createLibraryFile(title, destFolder, newFileKind, { content });
        lastPath = row.relative_path ?? row.filename;
        imported += 1;
      }
      await refresh();
      if (lastPath) setSelectedNote(lastPath);
      const skipMsg = skipped > 0 ? ` · skipped ${skipped} unsupported` : "";
      setToast(`Imported ${imported} note${imported === 1 ? "" : "s"}${skipMsg}`);
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not import files");
    } finally {
      setImporting(false);
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
      noteTopics.length > 0
        ? "Walking each lecture topic in order (small context) then combining…"
        : "Starting quiz generation…",
    );
    setError(null);
    try {
      const folderPath =
        selectedNote && selectedNote.includes("/")
          ? selectedNote.replace(/\\/g, "/").split("/").slice(0, -1).join("/")
          : folderForSave;
      if (noteTopics.length > 0) {
        setIntelStatus(
          selectedTopicIds.length
            ? `Topic loop (${selectedTopicIds.length} topics)…`
            : `Topic loop (${noteTopics.length} topics)…`,
        );
      } else {
        setIntelStatus("Calling AI (quiz_gen)…");
      }
      const result = await runWithBudgetConfirm((llm) =>
        generateLibraryQuiz(sourcePaths, {
          count: noteTopics.length > 0
            ? Math.max(quizCount, noteTopics.length * 2)
            : quizCount,
          focus: quizFocus === "cover_all" ? "mixed" : quizFocus,
          topic: noteTitle.trim() || primaryMeta?.title,
          llm,
          expandSiblings: false,
          save: true,
          seedDeck: true,
          folderPath,
          // Empty = walk every topic (the accurate engine). Selection only narrows.
          topicIds: selectedTopicIds.length > 0 ? selectedTopicIds : undefined,
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
      const deckHint =
        result.deck_id != null
          ? ` · deck #${result.deck_id}${result.cards_seeded ? ` (${result.cards_seeded} SRS)` : ""}`
          : "";
      const coverHint =
        result.topics_covered?.length || result.sections_covered?.length
          ? ` · ${result.topics_covered?.length || result.sections_covered?.length} topics`
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
          `Quiz draft from note facts (LLM offline / failed)${fileHint}${callHint} — check AI in Settings`,
        );
      } else if (result.source === "mixed") {
        setToast(
          `Partial AI quiz: ${result.questions.length} Qs${fillHint}${coverHint}${deckHint}${saveHint} — review carefully`,
        );
        if (result.saved) void refresh();
      } else {
        setToast(
          `Quiz ready: ${result.questions.length} Qs${callHint}${fillHint}${coverHint}${deckHint}${saveHint} — tagged for review`,
        );
        if (result.saved) void refresh();
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
    <div
      ref={fullscreenRootRef}
      className={
        notesFullscreen
          ? "study-library-page study-library-page--fullscreen flex flex-col min-h-0"
          : "study-library-page flex flex-col min-h-0"
      }
      style={{ "--lecture-note-size": `${NOTE_FONT_STEPS[noteFontStep]}rem` } as CSSProperties}
    >
      <div className="relative z-10 flex flex-col h-full min-h-0 p-4 gap-3">
        <header className="study-library-glass flex flex-col gap-2 px-3 py-2 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {!notesFullscreen ? (
            <Button
              type="button"
              size="icon"
              variant={fileManagerCollapsed ? "outline" : "secondary"}
              className="h-8 w-8 shrink-0"
              onClick={() => setFileManagerCollapsed((c) => !c)}
              title={fileManagerCollapsed ? "Show files" : "Hide files"}
              aria-label={fileManagerCollapsed ? "Show files" : "Hide files"}
              aria-pressed={!fileManagerCollapsed}
            >
              {fileManagerCollapsed ? (
                <PanelLeftOpen className="w-4 h-4" />
              ) : (
                <PanelLeftClose className="w-4 h-4" />
              )}
            </Button>
            ) : (
            <Button
              type="button"
              size="icon"
              variant="secondary"
              className="h-8 w-8 shrink-0"
              onClick={exitNotesFullscreen}
              title="Exit fullscreen (Esc)"
              aria-label="Exit fullscreen"
            >
              <Minimize2 className="w-4 h-4" />
            </Button>
            )}

            <div
              ref={setDocChromeHost}
              className="min-w-0 flex-1 flex items-center"
              aria-label="Current note"
            />

            <div className="hidden md:block h-6 w-px shrink-0 bg-border/70" aria-hidden />

            <div className="flex items-center gap-1 shrink-0">
              {!notesFullscreen ? (
                <>
              <select
                value={llmTier}
                onChange={(e) => setLlmTier(e.target.value)}
                className="h-8 max-w-[5.5rem] rounded-md border border-border bg-background/60 px-1.5 text-xs text-foreground"
                title="LLM tier for note AI actions"
                aria-label="LLM tier"
              >
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="heavy">Heavy</option>
              </select>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 text-xs px-2"
                onClick={() => setCreateSheetOpen(true)}
                title="New note from captions"
              >
                <Plus className="w-3.5 h-3.5" />
                <span className="hidden lg:inline ml-1">Captions</span>
              </Button>
              {tab === "library" && (
                <Button
                  type="button"
                  size="sm"
                  variant={studyToolsOpen ? "default" : "outline"}
                  className="h-8 text-xs px-2"
                  onClick={() => setStudyToolsOpen((o) => !o)}
                  title="Study tools"
                >
                  <PanelRight className="w-3.5 h-3.5" />
                  <span className="hidden xl:inline ml-1">Tools</span>
                </Button>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8"
                    title="More"
                    aria-label="More"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[11rem]">
                  <DropdownMenuItem asChild>
                    <Link to="/review?tab=due&source=lecture_notes">Review Hub</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/system-logs" className="flex items-center gap-2">
                      <ScrollText className="w-4 h-4" />
                      Logs
                    </Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
                </>
              ) : null}
            </div>
          </div>

          {navItems.length > 1 && !notesFullscreen && (
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
          {!fileManagerCollapsed && !notesFullscreen && (
            <aside className="study-library-glass study-library-sidebar study-library-sidebar--expanded shrink-0 flex flex-col min-h-0 overflow-hidden">
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
                    onImportFiles={(files, dest) => void handleImportFiles(files, dest)}
                    importing={importing}
                    viewMode={libraryViewMode}
                    onViewModeChange={setLibraryViewMode}
                    summarizingFolder={summarizingFolder}
                    onCollapse={() => setFileManagerCollapsed(true)}
                  />
                ) : null}
              </div>
            </aside>
          )}

          <div className="flex-1 flex flex-col min-w-0 min-h-0 gap-2">
            {/* Note/content fetch errors use toast — no sticky red banner here */}

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
              chromeHost={!showCompare ? docChromeHost : null}
              fullscreen={notesFullscreen}
              onToggleFullscreen={toggleNotesFullscreen}
              noteFontStep={noteFontStep}
              noteFontMax={NOTE_FONT_STEPS.length - 1}
              onNoteFontStep={bumpNoteFont}
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
          ) : studyToolsOpen && !notesFullscreen ? (
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
                setQuizFocus(f === "cover_all" ? "mixed" : f);
              }}
              noteTopics={noteTopics}
              selectedTopicIds={selectedTopicIds}
              onSelectedTopicIdsChange={setSelectedTopicIds}
              topicsLoading={topicsLoading}
              onGenerateQuiz={() => void handleGenerateQuiz()}
              onGenerateDrills={() => void handleGenerateDrills()}
              onPasteQuiz={(text) => void handlePasteQuiz(text)}
              onRemoveQuestion={(id) =>
                setQuizQuestions((prev) => prev.filter((q) => q.id !== id))
              }
              onGeneratePrimer={undefined}
              corpusGroundedNotes={false}
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
        onGenerateGrounded={undefined}
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
