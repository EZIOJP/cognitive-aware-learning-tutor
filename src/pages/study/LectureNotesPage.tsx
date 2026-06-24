import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { buildStudyQuizConfig } from "../../api/globalQuizClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import {
  BookOpen,
  ClipboardList,
  Loader2,
  PanelRight,
  Plus,
  Search,
  X,
} from "lucide-react";
import {
  captureMainAreaPng,
  createLibraryFile,
  createLibraryFolder,
  deleteLibraryFile,
  deleteLibraryFolder,
  exportNoteFile,
  exportLibraryFolder,
  fetchLibraryTree,
  generateLibraryDrills,
  generateLibraryQuiz,
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
  repairAllNoteBlocks,
  saveNoteContent,
  summarizeLibraryFolder,
  syncStudySession,
  updateLibraryFile,
  updateReadingState,
  uploadSnapshot,
  type GapAnalysisResult,
  type LibraryTree,
  type LlmConfig,
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
import { findLibraryFile } from "../../components/study/studyLibraryUtils";
import { extractBlockSurroundingContext, extractSelectionSurroundingContext, replaceFencedBlock } from "../../components/study/noteBlockUtils";
import { repairNoteMarkdown } from "../../components/study/markdownRepair";
import { sanitizeMermaidSource } from "../../components/study/mermaidSanitize";
import { StudyLibraryViewer } from "../../components/study/StudyLibraryViewer";
import { StudyLibraryCreateSheet } from "../../components/study/StudyLibraryCreateSheet";
import { Button } from "../../app/components/ui/button";

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
  const [tab, setTab] = useState<LibraryTab>("library");
  const [workflowStep, setWorkflowStep] = useState<StudyWorkflowStep>(0);
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
  const [readingOverrides, setReadingOverrides] = useState<
    Record<string, { read_scroll_top?: number; bookmark_scroll_top?: number | null }>
  >({});
  const [openScrollTop, setOpenScrollTop] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const activeNoteRef = useRef("");
  const [newFileKind, setNewFileKind] = useState("note");
  const [content, setContent] = useState("");
  const [compareContents, setCompareContents] = useState<[string, string]>(["", ""]);
  const [gapAnalysis, setGapAnalysis] = useState<GapAnalysisResult | null>(null);
  const [gapLoading, setGapLoading] = useState(false);
  const [intelGenerating, setIntelGenerating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [sessionItems, setSessionItems] = useState<StudySessionItem[]>([]);
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [drills, setDrills] = useState<CodeDrill[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<{
    domain: "study" | "code";
    config: Record<string, unknown>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [snapshotting, setSnapshotting] = useState(false);
  const [notesSemantic, setNotesSemantic] = useState(false);
  const [notesFast, setNotesFast] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmProvider, setLlmProvider] = useState(() => loadLlmPrefs().llm_provider ?? "lmstudio");
  const [llmBaseUrl, setLlmBaseUrl] = useState(() => loadLlmPrefs().llm_base_url ?? "http://127.0.0.1:1234");
  const [llmModel, setLlmModel] = useState(() => loadLlmPrefs().llm_model ?? "google/gemma-4-e4b");
  const [regeneratingBlock, setRegeneratingBlock] = useState<number | null>(null);

  const llmOverrides = {
    llm_provider: llmProvider,
    llm_base_url: llmBaseUrl.trim(),
    llm_model: llmModel.trim(),
  };

  const compareMode = comparePaths.length >= 2;
  const showCompare = compareMode && (tab === "gap" || tab === "review");

  useEffect(() => {
    saveLlmPrefs(llmOverrides);
  }, [llmProvider, llmBaseUrl, llmModel]);

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
    void refresh();
  }, [refresh]);

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
        const text = await getNoteContent(selectedNote);
        setContent(text);
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
        setCompareContents([a, b]);
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
        const result = await runGapAnalysis(comparePaths[0], comparePaths[1], llmOverrides);
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
  }, [comparePaths, tab, llmProvider, llmBaseUrl, llmModel]);

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

  const handleSaveNoteContent = useCallback(
    async (path: string, body: string) => {
      await saveNoteContent(path, body);
      setContent(body);
      void indexNote(path).catch(() => undefined);
      setToast("Note saved");
      setTimeout(() => setToast(null), 2500);
    },
    [],
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
      if (!selectedNote) return;
      const base = repairNoteMarkdown(content);
      const blockBody =
        _language === "mermaid" ? sanitizeMermaidSource(newBlockContent) : newBlockContent;
      const updated = replaceFencedBlock(base, blockIndex, blockBody);
      await saveNoteContent(selectedNote, updated);
      setContent(updated);
      void indexNote(selectedNote).catch(() => undefined);
      setToast("Block saved");
      setTimeout(() => setToast(null), 2500);
    },
    [content, selectedNote],
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
          note_context: extractBlockSurroundingContext(repairNoteMarkdown(content), blockIndex, {
            blockContent,
          }),
          llm: llmOverrides,
        });
        return result.content;
      } finally {
        setRegeneratingBlock(null);
      }
    },
    [content, llmProvider, llmBaseUrl, llmModel],
  );

  const handleSelectionRegenerate = useCallback(
    async ({
      selection,
      start,
      end,
      noteMarkdown,
      lang,
    }: {
      selection: string;
      start: number;
      end: number;
      noteMarkdown: string;
      lang: string | null;
    }) => {
      const base = repairNoteMarkdown(noteMarkdown);

      const applyMermaidSanitize = (text: string): string => {
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

      const isMermaid = lang === "mermaid" || /```mermaid/i.test(selection) || /^(graph|flowchart)\s/im.test(selection.trim());

      try {
        const result = await regenerateNoteSelection({
          selection,
          note_context: extractSelectionSurroundingContext(base, start, end),
          llm: llmOverrides,
        });
        return applyMermaidSanitize(result.content);
      } catch (err) {
        if (isMermaid) {
          const local = applyMermaidSanitize(selection);
          if (local.trim() !== selection.trim()) return local;
        }
        throw err;
      }
    },
    [llmProvider, llmBaseUrl, llmModel],
  );

  const handleRepairAllBlocks = useCallback(async () => {
    if (!selectedNote || !content.trim()) return;
    try {
      const result = await repairAllNoteBlocks({
        content: repairNoteMarkdown(content),
        use_llm: true,
        llm: llmOverrides,
      });
      await saveNoteContent(selectedNote, result.content);
      setContent(result.content);
      void indexNote(selectedNote).catch(() => undefined);
      const n = result.fixed_count;
      setToast(n > 0 ? `Fixed ${n} block${n === 1 ? "" : "s"} with AI` : "No broken blocks found");
      setTimeout(() => setToast(null), 4000);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not repair blocks");
      throw e;
    }
  }, [content, selectedNote, llmProvider, llmBaseUrl, llmModel]);

  const handleRepairSyntaxOnly = useCallback(async () => {
    if (!selectedNote || !content.trim()) return;
    try {
      const result = await repairAllNoteBlocks({
        content: repairNoteMarkdown(content),
        use_llm: false,
      });
      await saveNoteContent(selectedNote, result.content);
      setContent(result.content);
      void indexNote(selectedNote).catch(() => undefined);
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
      const result = await summarizeLibraryFolder(folderPath, undefined, llmOverrides);
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

  const handleGenerate = async () => {
    if (!selectedTranscript) return;
    setGenerating(true);
    setError(null);
    const referencePaths = comparePaths.filter((p) => /\.(pdf|md|ipynb)$/i.test(p));
    try {
      const result = await generateNotes(selectedTranscript, {
        title: noteTitle.trim() || undefined,
        topic: noteTitle.trim() || undefined,
        folderPath: folderForSave,
        referencePaths: referencePaths.length ? referencePaths : undefined,
        contextFolder: folderForSave || undefined,
        useSemanticGrouping: notesSemantic,
        fastMode: notesFast,
        llm: llmOverrides,
      });
      await refresh();
      setSelectedNote(result.filename);
      void indexNote(result.filename).catch(() => undefined);
      setCreateSheetOpen(false);
      setToast("Notes generated");
      setTimeout(() => setToast(null), 3000);
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
      const result = await generateNotesFromToday({
        title: noteTitle.trim() || undefined,
        topic: noteTitle.trim() || undefined,
        folderPath: folderForSave,
        useSemanticGrouping: notesSemantic,
        fastMode: notesFast,
        llm: llmOverrides,
      });
      await refresh();
      setSelectedNote(result.filename);
      void indexNote(result.filename).catch(() => undefined);
      setCreateSheetOpen(false);
      setToast("Notes generated from today");
      setTimeout(() => setToast(null), 3000);
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
    setError(null);
    try {
      const result = await generateLibraryQuiz(sourcePaths, {
        count: 5,
        topic: noteTitle.trim() || primaryMeta?.title,
        llm: llmOverrides,
      });
      setQuizQuestions(result.questions);
      addSessionItem(result.session_item);
      setToast(`Quiz generated (${result.source ?? "ok"})`);
      setTimeout(() => setToast(null), 3000);
      return result.questions;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Quiz generation failed");
      return [];
    } finally {
      setIntelGenerating(false);
    }
  };

  const handleTestKnowledge = async () => {
    if (sourcePaths.length === 0) {
      setError("Select a lecture note in the library first.");
      return;
    }
    const notePath = selectedNote || primaryMeta?.relative_path || "";
    let questions = quizQuestions;
    if (questions.length === 0) {
      questions = await handleGenerateQuiz();
    }
    if (questions.length === 0) return;
    setActiveQuiz({
      domain: "study",
      config: buildStudyQuizConfig(
        questions,
        drills,
        notePath,
        noteTitle.trim() || primaryMeta?.title,
      ),
    });
  };

  const handleGenerateDrills = async () => {
    if (sourcePaths.length === 0) return;
    setIntelGenerating(true);
    setError(null);
    try {
      const result = await generateLibraryDrills(sourcePaths, {
        count: 2,
        topic: noteTitle.trim() || primaryMeta?.title,
        llm: llmOverrides,
      });
      setDrills(result.drills);
      addSessionItem(result.session_item);
      setToast(`Drills generated (${result.source ?? "ok"})`);
      setTimeout(() => setToast(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Drill generation failed");
    } finally {
      setIntelGenerating(false);
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
            <h1 className="text-lg font-bold text-white tracking-wide">Study Library</h1>
            <p className="text-xs text-emerald-200/60">Read, edit, and export your lecture notes</p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs border-emerald-800/50"
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
                className="h-8 text-xs border-emerald-800/50"
                onClick={() => setStudyToolsOpen((o) => !o)}
              >
                <PanelRight className="w-3.5 h-3.5 mr-1.5" />
                Study tools
              </Button>
            )}
            <Button size="sm" variant="ghost" className="h-8 text-xs" asChild>
              <Link to="/review?tab=due&source=lecture_notes">Review Hub</Link>
            </Button>
          </div>

          {navItems.length > 1 && (
            <nav className="flex items-center gap-4 text-sm font-medium w-full sm:w-auto border-t sm:border-t-0 border-emerald-900/30 pt-2 sm:pt-0">
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

          {toast && <span className="text-xs text-emerald-400">{toast}</span>}
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
          <aside className="study-library-glass w-[min(340px,38vw)] min-w-[260px] shrink-0 flex flex-col min-h-0 overflow-hidden">
            <div className="flex-1 min-h-0 overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
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
                />
              ) : null}
            </div>
          </aside>

          <div className="flex-1 flex flex-col min-w-0 min-h-0 gap-2">
            {error && !loading && (
              <p className="text-xs text-red-400 shrink-0 px-1">{error}</p>
            )}

            {comparePaths.length > 0 && tab === "library" && (
              <div className="study-library-compare-bar shrink-0">
                <span className="text-xs text-emerald-200/80 truncate">
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
                    className="h-7 text-xs shrink-0 border-emerald-800/50"
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
              quizDisabled={!llmConfig?.reachable}
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
              onGenerateQuiz={() => void handleGenerateQuiz()}
              onGenerateDrills={() => void handleGenerateDrills()}
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
        llmConfig={llmConfig}
        generating={generating}
        snapshotting={snapshotting}
        onGenerate={() => void handleGenerate()}
        onGenerateToday={() => void handleGenerateToday()}
        onSnapshot={() => void handleSnapshot()}
        referenceHint={referenceHint || undefined}
      />
      {activeQuiz && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl bg-background shadow-xl">
            <GlobalQuizRunner
              domain={activeQuiz.domain}
              config={activeQuiz.config}
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
