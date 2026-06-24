import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { buildStudyQuizConfig } from "../../api/globalQuizClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import {
  BookOpen,
  Brain,
  Camera,
  ChevronDown,
  ClipboardList,
  Loader2,
  Play,
  Search,
  Sparkles,
} from "lucide-react";
import {
  captureMainAreaPng,
  createLibraryFile,
  createLibraryFolder,
  deleteLibraryFile,
  deleteLibraryFolder,
  fetchLibraryTree,
  generateLibraryDrills,
  generateLibraryQuiz,
  generateNotes,
  generateNotesFromToday,
  indexNote,
  getLlmConfig,
  getNoteContent,
  listNoteTopics,
  listTranscripts,
  loadLlmPrefs,
  runGapAnalysis,
  saveLlmPrefs,
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
import { StudyLibraryViewer } from "../../components/study/StudyLibraryViewer";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../app/components/ui/select";
import { cn } from "../../app/components/ui/utils";

type LibraryTab = "library" | "gap" | "review";

const NOTE_KINDS = [
  { value: "lecture", label: "Lecture" },
  { value: "textbook", label: "Textbook" },
  { value: "quiz", label: "Quiz" },
  { value: "exercise", label: "Exercise" },
  { value: "note", label: "Note" },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function folderOf(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length <= 1 ? "" : parts.slice(0, -1).join("/");
}

export function LectureNotesPage() {
  const [tab, setTab] = useState<LibraryTab>("library");
  const [workflowStep, setWorkflowStep] = useState<StudyWorkflowStep>(0);
  const [toolsOpen, setToolsOpen] = useState(false);

  const [transcripts, setTranscripts] = useState<TranscriptFile[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [libraryTree, setLibraryTree] = useState<LibraryTree | null>(null);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [selectedNote, setSelectedNote] = useState("");
  const [comparePaths, setComparePaths] = useState<string[]>([]);
  const [selectedTranscript, setSelectedTranscript] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [summarizingFolder, setSummarizingFolder] = useState("");
  const [libraryViewMode, setLibraryViewMode] = useState<"grid" | "list">("grid");
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

  const llmOverrides = {
    llm_provider: llmProvider,
    llm_base_url: llmBaseUrl.trim(),
    llm_model: llmModel.trim(),
  };

  const compareMode = comparePaths.length >= 2;
  const showCompare = compareMode;

  useEffect(() => {
    saveLlmPrefs(llmOverrides);
  }, [llmProvider, llmBaseUrl, llmModel]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, top, tree, llm] = await Promise.all([
        listTranscripts(),
        listNoteTopics(),
        fetchLibraryTree(),
        getLlmConfig().catch(() => null),
      ]);
      setTranscripts(t);
      setTopics(top);
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
    { id: "gap", label: "Gap Analysis", icon: Search },
    { id: "review", label: "Review & Sync", icon: ClipboardList },
  ];

  return (
    <div className="study-library-page flex flex-col min-h-0">
      <StudyLibraryBackground />

      <div className="relative z-10 flex flex-col h-full min-h-0 p-4 gap-3">
        <header className="study-library-glass flex items-center justify-between px-5 py-3 shrink-0">
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide">Study Library</h1>
            <p className="text-[11px] text-emerald-200/60">
              Lectures · textbooks · quizzes · AI cross-check
            </p>
          </div>
          <nav className="flex items-center gap-5 text-sm font-medium">
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
          {toast && <span className="text-xs text-emerald-400 ml-4">{toast}</span>}
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
          <aside className="study-library-glass w-[min(440px,44vw)] min-w-[300px] shrink-0 flex flex-col p-2 min-h-0">
            <div className="flex-1 min-h-0 overflow-hidden rounded-lg border border-emerald-900/30 bg-black/15">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                </div>
              ) : error && !libraryTree ? (
                <p className="text-[10px] text-red-400 p-3">{error}</p>
              ) : libraryTree ? (
                <StudyLibraryExplorer
                  tree={libraryTree}
                  browsePath={selectedFolder}
                  selectedFile={selectedNote}
                  onBrowsePath={setSelectedFolder}
                  onSelectFile={setSelectedNote}
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

            <button
              type="button"
              onClick={() => setToolsOpen((o) => !o)}
              className="mt-2 pt-2 border-t border-emerald-900/40 flex items-center justify-between text-[11px] text-emerald-300/80 hover:text-emerald-200 shrink-0"
            >
              Live captions → notes
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", toolsOpen && "rotate-180")} />
            </button>
            {toolsOpen && (
              <div className="mt-2 space-y-2 shrink-0">
                <Select value={selectedTranscript} onValueChange={setSelectedTranscript}>
                  <SelectTrigger className="h-7 text-[10px] bg-black/20 border-emerald-900/40">
                    <SelectValue placeholder="Transcript" />
                  </SelectTrigger>
                  <SelectContent>
                    {transcripts.map((t) => (
                      <SelectItem key={t.filename} value={t.filename} className="text-xs">
                        {t.filename} ({formatSize(t.size_bytes)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  className="h-7 text-[10px] bg-black/20 border-emerald-900/40"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  placeholder="Note title (optional)"
                />
                <p className="text-[9px] text-emerald-200/50 leading-snug">
                  Default: fast mode (few LLM calls). Enable topic grouping for richer notes.
                  Compare PDF/Colab files in the library to attach references by filename.
                </p>
                <div className="grid grid-cols-2 gap-1 text-[9px] text-emerald-100/80">
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={notesSemantic}
                      onChange={(e) => setNotesSemantic(e.target.checked)}
                      className="rounded"
                    />
                    Topic grouping
                  </label>
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={notesFast}
                      onChange={(e) => setNotesFast(e.target.checked)}
                      className="rounded"
                    />
                    Fast (transcript only)
                  </label>
                </div>
                {comparePaths.some((p) => /\.(pdf|md|ipynb)$/i.test(p)) && (
                  <p className="text-[9px] text-emerald-300/70">
                    References:{" "}
                    {comparePaths
                      .filter((p) => /\.(pdf|md|ipynb)$/i.test(p))
                      .map((p) => p.split("/").pop())
                      .join(", ")}
                  </p>
                )}
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 h-7 text-[10px] border-emerald-800/50"
                    disabled={snapshotting || !selectedTranscript}
                    onClick={() => void handleSnapshot()}
                  >
                    <Camera className="w-3 h-3 mr-1" />
                    Slide
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1 h-7 text-[10px]"
                    disabled={generating || !selectedTranscript}
                    onClick={() => void handleGenerate()}
                  >
                    {generating ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <>
                        <Sparkles className="w-3 h-3 mr-1" />
                        Generate
                      </>
                    )}
                  </Button>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="w-full h-7 text-[10px]"
                  disabled={generating}
                  onClick={() => void handleGenerateToday()}
                >
                  From today
                </Button>
                {topics.length > 0 && (
                  <p className="text-[9px] text-emerald-200/50 truncate">Topics: {topics.slice(0, 2).join(", ")}</p>
                )}
                <p className="text-[9px] text-emerald-200/50">
                  {llmConfig?.reachable ? `LLM OK · ${llmConfig.model}` : "Set OLLAMA_ENABLED=1"}
                </p>
              </div>
            )}
          </aside>

          <div className="flex-1 flex flex-col min-w-0 min-h-0 gap-2">
            {error && !loading && (
              <p className="text-xs text-red-400 shrink-0">{error}</p>
            )}
            {tab === "library" && selectedNote && content && !showCompare && (
              <div className="gloss-panel shrink-0 rounded-xl border-2 border-primary/50 bg-primary/10 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-primary flex items-center gap-2">
                    <Brain className="h-4 w-4 shrink-0" />
                    Test your knowledge
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {quizQuestions.length > 0
                      ? `${quizQuestions.length} questions ready — take the quiz to seed your review queue.`
                      : "One click: generate MCQs from this note, then practice (FSRS cards created on each answer)."}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  <Button
                    size="sm"
                    className="gap-1.5 text-primary-foreground"
                    disabled={intelGenerating || !llmConfig?.reachable}
                    onClick={() => void handleTestKnowledge()}
                  >
                    {intelGenerating ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    {quizQuestions.length > 0 ? "Take quiz" : "Generate & take quiz"}
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <Link to="/review?tab=due&source=lecture_notes">Review Hub</Link>
                  </Button>
                </div>
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
              onScrollContainer={(el) => {
                scrollContainerRef.current = el;
              }}
              onSetBookmark={(path, top) => void handleSetBookmark(path, top)}
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
          ) : (
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
          )}
        </main>
      </div>
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
