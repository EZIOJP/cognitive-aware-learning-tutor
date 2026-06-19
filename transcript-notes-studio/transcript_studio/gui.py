"""Tkinter GUI — Summarize (browse & combine) and Transcribe (separate) workflows."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import customtkinter as ctk

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    USE_CTK = True
except ImportError:
    USE_CTK = False
    ctk = None  # type: ignore[misc, assignment]

from transcript_studio.config import load_config, save_config
from transcript_studio.llm_client import llm_reachable, options_from_config
from transcript_studio.notes_generator import (
    combine_source_files,
    generate_notes_from_files,
    generate_notes_from_text,
    list_transcripts,
    parse_transcript,
    resolve_session_snapshots_dir,
)
from transcript_studio.source_loader import SOURCE_EXTENSIONS, check_pdf_deps, load_source_file, prepare_sources
from transcript_studio.live_captions import LiveCaptionsScraper, check_captions_deps, ensure_windows
from transcript_studio.snapshots import CaptureSession, merge_slides_into_transcript
from transcript_studio.whisper_client import (
    WHISPER_PRESETS,
    check_whisper_deps,
    save_transcript,
    transcribe_audio,
)
from transcript_studio.whisper_live import (
    LiveWhisperSession,
    check_live_whisper_deps,
    check_system_audio_available,
)

log = logging.getLogger(__name__)

_AppBase = ctk.CTk if USE_CTK else tk.Tk
_Frame = ctk.CTkFrame if USE_CTK else ttk.Frame
_Button = ctk.CTkButton if USE_CTK else ttk.Button
_Label = ctk.CTkLabel if USE_CTK else ttk.Label
_Entry = ctk.CTkEntry if USE_CTK else ttk.Entry
_Checkbox = ctk.CTkCheckBox if USE_CTK else ttk.Checkbutton


class TranscriptStudioApp(_AppBase):
    def __init__(self) -> None:
        super().__init__()
        self.title("Transcript Notes Studio")
        self.minsize(900, 640)
        self.geometry("1000x720")

        self.cfg = load_config()
        self._raw_text = ""
        self._cleaned_text = ""
        self._busy = False
        self._summarizing = False
        self._summarize_cancel = threading.Event()
        self._transcribing = False
        self._captions_running = False
        self._captions_stop = threading.Event()
        self._captions_scraper: LiveCaptionsScraper | None = None
        self._live_whisper_running = False
        self._live_whisper_stop = threading.Event()
        self._live_whisper_session: LiveWhisperSession | None = None
        self._capture_session: CaptureSession | None = None
        self._source_files: list[Path] = []
        self._last_transcript_path: Path | None = None

        self._build_ui()
        self._refresh_library_list()
        self._load_fields_from_config()

    # ------------------------------------------------------------------ UI shell

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        self.mode_notebook = ttk.Notebook(outer)
        self.mode_notebook.pack(fill=tk.BOTH, expand=True)

        self.summarize_tab = _Frame(self.mode_notebook, padding=4) if not USE_CTK else _Frame(self.mode_notebook)
        self.captions_tab = ttk.Frame(self.mode_notebook, padding=4)
        self.transcribe_tab = ttk.Frame(self.mode_notebook, padding=4)
        self.mode_notebook.add(self.summarize_tab, text="  Summarize & combine  ")
        self.mode_notebook.add(self.captions_tab, text="  Live Captions  ")
        self.mode_notebook.add(self.transcribe_tab, text="  Transcribe audio  ")

        self._build_summarize_tab()
        self._build_captions_tab()
        self._build_transcribe_tab()

        self.status_var = tk.StringVar(
            value="Ready — Summarize existing .txt, capture Live Captions, or transcribe audio"
        )
        ttk.Label(outer, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, pady=(6, 0)
        )

    def _build_summarize_tab(self) -> None:
        tab = self.summarize_tab

        # --- Source files ---
        src = ttk.LabelFrame(tab, text="Source files — .txt transcript + .pdf / .ipynb / .md references", padding=8)
        src.pack(fill=tk.X, pady=(0, 6))

        src_btns = ttk.Frame(src)
        src_btns.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(src_btns, text="Add file(s)…", command=self._add_source_files).pack(side=tk.LEFT)
        ttk.Button(src_btns, text="Add folder…", command=self._add_source_folder).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(src_btns, text="Remove", command=self._remove_source_file).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(src_btns, text="Clear", command=self._clear_source_files).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(src_btns, text="From library", command=self._add_from_library).pack(side=tk.LEFT, padx=(12, 0))

        src_paned = ttk.Panedwindow(src, orient=tk.HORIZONTAL)
        src_paned.pack(fill=tk.BOTH, expand=True)

        lib_col = ttk.Frame(src_paned, width=180)
        src_paned.add(lib_col, weight=0)
        ttk.Label(lib_col, text="Library (data/transcripts)").pack(anchor=tk.W)
        self.library_list = tk.Listbox(lib_col, height=5, exportselection=False)
        self.library_list.pack(fill=tk.BOTH, expand=True, pady=2)
        self.library_list.bind("<Double-Button-1>", self._on_library_double_click)

        sel_col = ttk.Frame(src_paned)
        src_paned.add(sel_col, weight=1)
        ttk.Label(sel_col, text="Selected for this run (order = combine order)").pack(anchor=tk.W)
        self.source_list = tk.Listbox(sel_col, height=5, exportselection=False, selectmode=tk.EXTENDED)
        self.source_list.pack(fill=tk.BOTH, expand=True, pady=2)
        self.source_list.bind("<<ListboxSelect>>", self._on_source_select)

        # --- Output & options ---
        opts = ttk.LabelFrame(tab, text="Notes output & options", padding=8)
        opts.pack(fill=tk.X, pady=(0, 6))

        r1 = ttk.Frame(opts)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="Title").pack(side=tk.LEFT)
        self.title_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.title_var, width=28).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(r1, text="Output folder").pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="…", width=3, command=self._browse_output).pack(side=tk.LEFT)

        r2 = ttk.Frame(opts)
        r2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(r2, text="Context folder").pack(side=tk.LEFT)
        self.context_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.context_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r2, text="…", width=3, command=self._browse_context).pack(side=tk.LEFT)

        r3 = _Frame(opts) if USE_CTK else ttk.Frame(opts)
        r3.pack(fill=tk.X, pady=(6, 0))
        self.aggressive_var = tk.BooleanVar(value=self.cfg.aggressive_dedup_default)
        self._add_checkbox(
            r3, "Aggressive dedup (Live Captions snapshots)", self.aggressive_var
        ).pack(side=tk.LEFT)
        self.refine_var = tk.BooleanVar(value=self.cfg.refine_second_pass)
        self._add_checkbox(r3, "2nd pass — stitch topics & refine flow", self.refine_var).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        self.enrich_var = tk.BooleanVar(value=self.cfg.enrich_with_references)
        self._add_checkbox(r3, "3rd pass — enrich with Colab/PDF examples", self.enrich_var).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        self.fast_var = tk.BooleanVar(value=self.cfg.fast_mode)
        self._add_checkbox(r3, "Fast mode (1 pass only)", self.fast_var).pack(side=tk.LEFT, padx=(12, 0))

        r4 = _Frame(opts) if USE_CTK else ttk.Frame(opts)
        r4.pack(fill=tk.X, pady=(6, 0))
        self.semantic_chunk_var = tk.BooleanVar(value=self.cfg.use_semantic_chunking)
        self._add_checkbox(r4, "Semantic chunking (embed-aware boundaries)", self.semantic_chunk_var).pack(
            side=tk.LEFT
        )
        self.tag_extract_var = tk.BooleanVar(value=self.cfg.use_tag_extraction)
        self._add_checkbox(r4, "LLM tag extraction & topic ordering", self.tag_extract_var).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        self.wikilinks_var = tk.BooleanVar(value=self.cfg.inject_wikilinks)
        self._add_checkbox(r4, "Auto wikilinks", self.wikilinks_var).pack(
            side=tk.LEFT, padx=(12, 0)
        )

        # --- LLM ---
        llm = ttk.LabelFrame(tab, text="Summarization LLM", padding=8)
        llm.pack(fill=tk.X, pady=(0, 6))

        lr1 = ttk.Frame(llm)
        lr1.pack(fill=tk.X)
        ttk.Label(lr1, text="Provider").pack(side=tk.LEFT)
        self.provider_var = tk.StringVar()
        ttk.Combobox(
            lr1, textvariable=self.provider_var,
            values=["lmstudio", "ollama", "openai"], width=10, state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(lr1, text="URL").pack(side=tk.LEFT)
        self.url_var = tk.StringVar()
        ttk.Entry(lr1, textvariable=self.url_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Label(lr1, text="Model").pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        ttk.Entry(lr1, textvariable=self.model_var, width=22).pack(side=tk.LEFT, padx=6)
        ttk.Label(lr1, text="Temp").pack(side=tk.LEFT, padx=(8, 0))
        self.temp_var = tk.StringVar(value=str(self.cfg.llm_temperature))
        ttk.Entry(lr1, textvariable=self.temp_var, width=5).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(lr1, text="Test", command=self._test_llm).pack(side=tk.LEFT, padx=(8, 0))

        # --- Actions ---
        actions = _Frame(tab) if USE_CTK else ttk.Frame(tab)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.parse_btn = self._add_button(actions, "Parse & preview", self._run_parse)
        self.parse_btn.pack(side=tk.LEFT)
        self.summarize_btn = self._add_button(actions, "Generate notes", self._run_summarize)
        self.summarize_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.cancel_summarize_btn = self._add_button(actions, "Cancel", self._cancel_summarize)
        self.cancel_summarize_btn.configure(state=tk.DISABLED)
        self.cancel_summarize_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._add_button(actions, "Open output folder", self._open_output).pack(side=tk.LEFT, padx=(8, 0))
        self._add_button(actions, "Save settings", self._save_settings).pack(side=tk.RIGHT)

        prog_row = _Frame(tab) if USE_CTK else ttk.Frame(tab)
        prog_row.pack(fill=tk.X, pady=(0, 6))
        self.progress_var = tk.DoubleVar(value=0.0)
        if USE_CTK:
            self.progress_bar = ctk.CTkProgressBar(prog_row)
            self.progress_bar.set(0)
        else:
            self.progress_bar = ttk.Progressbar(prog_row, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, expand=True)

        # --- Preview ---
        self.preview_notebook = ttk.Notebook(tab)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True)

        self.raw_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        self.clean_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 9))
        self.preview_notebook.add(self.raw_text, text="Combined raw")
        self.preview_notebook.add(self.clean_text, text="Cleaned preview")
        self.preview_notebook.add(self.log_text, text="Log")

    def _add_checkbox(self, parent, text: str, variable: tk.BooleanVar):
        if USE_CTK:
            return ctk.CTkCheckBox(parent, text=text, variable=variable)
        return ttk.Checkbutton(parent, text=text, variable=variable)

    def _add_button(self, parent, text: str, command):
        if USE_CTK:
            return ctk.CTkButton(parent, text=text, command=command)
        return ttk.Button(parent, text=text, command=command)

    def _build_captions_tab(self) -> None:
        tab = self.captions_tab

        intro = ttk.Label(
            tab,
            text="Capture Windows 11 Live Captions (Win+Ctrl+L) while you watch a lecture. "
                 "Press Start, then Stop when done — the .txt is saved to data/transcripts/. "
                 "Use Aggressive dedup on the Summarize tab for best results.",
            wraplength=900,
        )
        intro.pack(anchor=tk.W, pady=(0, 8))

        opts = ttk.LabelFrame(tab, text="Capture settings", padding=8)
        opts.pack(fill=tk.X, pady=(0, 6))

        r1 = ttk.Frame(opts)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="Method").pack(side=tk.LEFT)
        self.captions_method_var = tk.StringVar(value=self.cfg.captions_method)
        ttk.Combobox(
            r1, textvariable=self.captions_method_var,
            values=["uia", "ocr"], width=8, state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(r1, text="Poll (sec)").pack(side=tk.LEFT)
        self.captions_poll_var = tk.StringVar(value=str(self.cfg.captions_poll_interval))
        ttk.Entry(r1, textvariable=self.captions_poll_var, width=8).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(r1, text="Max duration (sec, 0=until Stop)").pack(side=tk.LEFT)
        self.captions_duration_var = tk.StringVar(value=str(self.cfg.captions_duration_sec))
        ttk.Entry(r1, textvariable=self.captions_duration_var, width=8).pack(side=tk.LEFT, padx=6)

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.captions_start_btn = ttk.Button(actions, text="Start capture", command=self._run_captions_start)
        self.captions_start_btn.pack(side=tk.LEFT)
        self.captions_stop_btn = ttk.Button(
            actions, text="Stop & save", command=self._run_captions_stop, state=tk.DISABLED
        )
        self.captions_stop_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Check deps", command=self._check_captions).pack(side=tk.LEFT, padx=(8, 0))
        self.captions_send_btn = ttk.Button(
            actions,
            text="Send last transcript → Summarize",
            command=self._send_to_summarize_from_captions,
            state=tk.DISABLED,
        )
        self.captions_send_btn.pack(side=tk.LEFT, padx=(16, 0))

        self.captions_log = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Consolas", 9), height=14)
        self.captions_log.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    def _build_transcribe_tab(self) -> None:
        tab = self.transcribe_tab

        intro = ttk.Label(
            tab,
            text="Whisper turns speech into text. File mode transcribes a recording; Live mic mode listens "
                 "and transcribes in chunks (uses faster-whisper, ~10s delay — not instant like Win+Ctrl+L). "
                 "For instant on-screen captions while watching video, use the Live Captions tab.",
            wraplength=900,
        )
        intro.pack(anchor=tk.W, pady=(0, 8))

        whisper_frame = ttk.LabelFrame(tab, text="From audio file", padding=8)
        whisper_frame.pack(fill=tk.X, pady=(0, 6))

        w1 = ttk.Frame(whisper_frame)
        w1.pack(fill=tk.X)
        ttk.Label(w1, text="Engine").pack(side=tk.LEFT)
        self.whisper_engine_var = tk.StringVar()
        ttk.Combobox(
            w1, textvariable=self.whisper_engine_var,
            values=["transformers", "faster-whisper"], width=14, state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(w1, text="Device").pack(side=tk.LEFT)
        self.whisper_device_var = tk.StringVar()
        ttk.Combobox(
            w1, textvariable=self.whisper_device_var,
            values=["auto", "cpu", "cuda:0"], width=8, state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(w1, text="Task").pack(side=tk.LEFT)
        self.whisper_task_var = tk.StringVar()
        ttk.Combobox(
            w1, textvariable=self.whisper_task_var,
            values=["transcribe", "translate"], width=10, state="readonly",
        ).pack(side=tk.LEFT, padx=6)

        w2 = ttk.Frame(whisper_frame)
        w2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(w2, text="Model").pack(side=tk.LEFT)
        self.whisper_preset_var = tk.StringVar()
        preset_names = [p[0] for p in WHISPER_PRESETS]
        self.whisper_preset_combo = ttk.Combobox(
            w2, textvariable=self.whisper_preset_var,
            values=preset_names, width=42, state="readonly",
        )
        self.whisper_preset_combo.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        self.whisper_preset_combo.bind("<<ComboboxSelected>>", self._on_whisper_preset)

        w3 = ttk.Frame(whisper_frame)
        w3.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(w3, text="Model ID").pack(side=tk.LEFT)
        self.whisper_model_var = tk.StringVar()
        ttk.Entry(w3, textvariable=self.whisper_model_var).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        ttk.Label(w3, text="Lang").pack(side=tk.LEFT, padx=(8, 0))
        self.whisper_lang_var = tk.StringVar()
        ttk.Entry(w3, textvariable=self.whisper_lang_var, width=10).pack(side=tk.LEFT, padx=4)

        w4 = ttk.Frame(whisper_frame)
        w4.pack(fill=tk.X, pady=(6, 0))
        self.audio_var = tk.StringVar()
        ttk.Entry(w4, textvariable=self.audio_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(w4, text="Browse audio…", command=self._browse_audio).pack(side=tk.LEFT)
        self.transcribe_btn = ttk.Button(w4, text="Transcribe → .txt", command=self._run_transcribe)
        self.transcribe_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(w4, text="Check Whisper", command=self._check_whisper).pack(side=tk.LEFT, padx=(6, 0))

        live_frame = ttk.LabelFrame(tab, text="Live Whisper (chunks)", padding=8)
        live_frame.pack(fill=tk.X, pady=(0, 6))

        l1 = ttk.Frame(live_frame)
        l1.pack(fill=tk.X)
        ttk.Label(l1, text="Audio source").pack(side=tk.LEFT)
        self.live_source_var = tk.StringVar(value=self._live_source_label(self.cfg.whisper_live_source))
        self.live_source_combo = ttk.Combobox(
            l1,
            textvariable=self.live_source_var,
            values=["System audio (speakers)", "Microphone"],
            width=24,
            state="readonly",
        )
        self.live_source_combo.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(l1, text="Chunk (sec)").pack(side=tk.LEFT)
        self.live_chunk_var = tk.StringVar(value=str(self.cfg.whisper_live_chunk_sec))
        ttk.Entry(l1, textvariable=self.live_chunk_var, width=8).pack(side=tk.LEFT, padx=(6, 16))
        self.live_start_btn = ttk.Button(l1, text="Start live", command=self._run_live_whisper_start)
        self.live_start_btn.pack(side=tk.LEFT)
        self.live_stop_btn = ttk.Button(
            l1, text="Stop & save", command=self._run_live_whisper_stop, state=tk.DISABLED
        )
        self.live_stop_btn.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(l1, text="Check live deps", command=self._check_live_whisper).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            live_frame,
            text="System audio captures what you hear (YouTube, Zoom, etc.) via Windows WASAPI loopback — "
                 "no mic or Stereo Mix needed. Still ~10s chunk delay; for instant captions use Live Captions tab.",
            font=("Segoe UI", 8),
            foreground="#888",
            wraplength=880,
        ).pack(anchor=tk.W, pady=(4, 0))

        snap_frame = ttk.LabelFrame(tab, text="Slide capture (optional, during file or live transcribe)", padding=8)
        snap_frame.pack(fill=tk.X, pady=(0, 6))

        s1 = ttk.Frame(snap_frame)
        s1.pack(fill=tk.X)
        self.capture_var = tk.BooleanVar(value=self.cfg.capture_enabled)
        ttk.Checkbutton(s1, text="Capture screenshots", variable=self.capture_var).pack(side=tk.LEFT)
        ttk.Label(s1, text="Auto every (sec)").pack(side=tk.LEFT, padx=(16, 0))
        self.capture_interval_var = tk.StringVar(value=str(self.cfg.capture_auto_interval_sec))
        ttk.Entry(s1, textvariable=self.capture_interval_var, width=8).pack(side=tk.LEFT, padx=4)
        self.snap_now_btn = ttk.Button(s1, text="Snap now", command=self._snap_now, state=tk.DISABLED)
        self.snap_now_btn.pack(side=tk.LEFT, padx=(12, 0))

        post = ttk.Frame(tab)
        post.pack(fill=tk.X, pady=(6, 0))
        self.send_summarize_btn = ttk.Button(
            post,
            text="Send last transcript → Summarize tab",
            command=self._send_to_summarize,
            state=tk.DISABLED,
        )
        self.send_summarize_btn.pack(side=tk.LEFT)

        self.transcribe_log = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Consolas", 9), height=12)
        self.transcribe_log.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # ------------------------------------------------------------------ Config

    def _load_fields_from_config(self) -> None:
        self.provider_var.set(self.cfg.llm_provider)
        self.url_var.set(self.cfg.llm_base_url)
        self.model_var.set(self.cfg.llm_model)
        self.output_var.set(str(self.cfg.notes_path()))
        self.refine_var.set(self.cfg.refine_second_pass)
        self.enrich_var.set(self.cfg.enrich_with_references)
        self.fast_var.set(self.cfg.fast_mode)
        self.temp_var.set(str(self.cfg.llm_temperature))
        self.aggressive_var.set(self.cfg.aggressive_dedup_default)
        if self.cfg.context_folder:
            self.context_var.set(self.cfg.context_folder)
        self.capture_var.set(self.cfg.capture_enabled)
        self.capture_interval_var.set(str(self.cfg.capture_auto_interval_sec))
        self.captions_method_var.set(self.cfg.captions_method)
        self.captions_poll_var.set(str(self.cfg.captions_poll_interval))
        self.captions_duration_var.set(str(self.cfg.captions_duration_sec))
        self.live_chunk_var.set(str(self.cfg.whisper_live_chunk_sec))
        self.live_source_var.set(self._live_source_label(self.cfg.whisper_live_source))
        self.whisper_engine_var.set(self.cfg.whisper_engine)
        self.whisper_device_var.set(self.cfg.whisper_device)
        self.whisper_task_var.set(self.cfg.whisper_task)
        self.whisper_lang_var.set(self.cfg.whisper_language)
        self.whisper_model_var.set(self.cfg.whisper_model)
        self._sync_whisper_preset_from_model()
        if self.cfg.last_audio_file and Path(self.cfg.last_audio_file).is_file():
            self.audio_var.set(self.cfg.last_audio_file)
        if self.cfg.last_transcript and Path(self.cfg.last_transcript).is_file():
            p = Path(self.cfg.last_transcript)
            self._add_paths([p], select_last=True)

    def _save_settings(self) -> None:
        self.cfg.llm_provider = self.provider_var.get()
        self.cfg.llm_base_url = self.url_var.get().strip()
        self.cfg.llm_model = self.model_var.get().strip()
        self.cfg.aggressive_dedup_default = self.aggressive_var.get()
        self.cfg.refine_second_pass = self.refine_var.get()
        self.cfg.enrich_with_references = self.enrich_var.get()
        self.cfg.fast_mode = self.fast_var.get()
        self.cfg.use_semantic_chunking = self.semantic_chunk_var.get()
        self.cfg.use_tag_extraction = self.tag_extract_var.get()
        self.cfg.inject_wikilinks = self.wikilinks_var.get()
        try:
            temp = float(self.temp_var.get().strip() or "0.3")
            self.cfg.llm_temperature = max(0.2, min(0.4, temp))
        except ValueError:
            self.cfg.llm_temperature = 0.3
        self.cfg.context_folder = self.context_var.get().strip()
        self.cfg.capture_enabled = self.capture_var.get()
        try:
            self.cfg.capture_auto_interval_sec = max(
                0.0, float(self.capture_interval_var.get().strip() or "0")
            )
        except ValueError:
            self.cfg.capture_auto_interval_sec = 120.0
        self.cfg.notes_dir = self.output_var.get().strip()
        if self._source_files:
            self.cfg.last_transcript = str(self._source_files[-1])
        self.cfg.whisper_engine = self.whisper_engine_var.get()
        self.cfg.whisper_model = self.whisper_model_var.get().strip()
        self.cfg.whisper_device = self.whisper_device_var.get()
        self.cfg.whisper_language = self.whisper_lang_var.get().strip()
        self.cfg.whisper_task = self.whisper_task_var.get()
        self.cfg.last_audio_file = self.audio_var.get().strip()
        self.cfg.captions_method = self.captions_method_var.get()
        try:
            self.cfg.captions_poll_interval = max(
                0.1, float(self.captions_poll_var.get().strip() or "0.5")
            )
        except ValueError:
            self.cfg.captions_poll_interval = 0.5
        try:
            self.cfg.captions_duration_sec = max(
                0.0, float(self.captions_duration_var.get().strip() or "0")
            )
        except ValueError:
            self.cfg.captions_duration_sec = 0.0
        try:
            self.cfg.whisper_live_chunk_sec = max(
                3.0, float(self.live_chunk_var.get().strip() or "10")
            )
        except ValueError:
            self.cfg.whisper_live_chunk_sec = 10.0
        self.cfg.whisper_live_source = self._live_source_value(self.live_source_var.get())
        save_config(self.cfg)
        self._log("Settings saved.")
        self.status_var.set("Settings saved")

    # ------------------------------------------------------------------ Source file list

    def _refresh_library_list(self) -> None:
        self.library_list.delete(0, tk.END)
        for p in list_transcripts():
            self.library_list.insert(tk.END, p.name)

    def _refresh_source_listbox(self) -> None:
        self.source_list.delete(0, tk.END)
        for p in self._source_files:
            self.source_list.insert(tk.END, p.name)

    def _add_paths(self, paths: list[Path], *, select_last: bool = False) -> None:
        added = False
        for path in paths:
            path = path.resolve()
            if not path.is_file():
                continue
            if path not in self._source_files:
                self._source_files.append(path)
                added = True
        if not added and not paths:
            return
        self._refresh_source_listbox()
        if select_last and self._source_files:
            self.source_list.selection_clear(0, tk.END)
            self.source_list.selection_set(len(self._source_files) - 1)
            self._load_combined_preview()
        elif added:
            self._load_combined_preview()

    def _add_source_files(self) -> None:
        ext_list = " ".join(f"*{e}" for e in sorted(SOURCE_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Select source file(s)",
            filetypes=[
                ("Sources", ext_list),
                ("PDF", "*.pdf"),
                ("Notebook", "*.ipynb"),
                ("Text", "*.txt"),
                ("Markdown", "*.md"),
                ("All files", "*.*"),
            ],
            initialdir=str(self.cfg.transcripts_path()),
        )
        if paths:
            self._add_paths([Path(p) for p in paths])

    def _add_source_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Folder with .txt / .pdf / .ipynb / .md sources",
            initialdir=str(self.cfg.transcripts_path()),
        )
        if not folder:
            return
        root = Path(folder)
        files: list[Path] = []
        for ext in SOURCE_EXTENSIONS:
            files.extend(root.glob(f"*{ext}"))
        files = sorted(set(files))
        if not files:
            messagebox.showinfo("No files", f"No supported source files in {folder}")
            return
        self._add_paths(files)

    def _add_from_library(self) -> None:
        sel = self.library_list.curselection()
        if not sel:
            messagebox.showinfo("Library", "Select a file in the library list first.")
            return
        paths = [self.cfg.transcripts_path() / self.library_list.get(i) for i in sel]
        self._add_paths(paths)

    def _on_library_double_click(self, _event: object) -> None:
        self._add_from_library()

    def _remove_source_file(self) -> None:
        sel = list(self.source_list.curselection())
        if not sel:
            return
        for i in reversed(sel):
            del self._source_files[i]
        self._refresh_source_listbox()
        self._load_combined_preview()

    def _clear_source_files(self) -> None:
        self._source_files.clear()
        self._refresh_source_listbox()
        self._raw_text = ""
        self.raw_text.delete("1.0", tk.END)
        self.status_var.set("Source list cleared")

    def _on_source_select(self, _event: object) -> None:
        if self._source_files:
            self._load_combined_preview()

    def _load_combined_preview(self) -> None:
        if not self._source_files:
            return
        try:
            transcript_text, reference_text, auto_aggressive = prepare_sources(self._source_files)
            self._raw_text = transcript_text
            if reference_text:
                self._raw_text += (
                    f"\n\n--- Reference materials ({len(reference_text):,} chars, not parsed as transcript) ---\n\n"
                    + reference_text[:8000]
                )
                if len(reference_text) > 8000:
                    self._raw_text += "\n\n… [reference preview truncated]"
            if auto_aggressive and not self.aggressive_var.get():
                self.aggressive_var.set(True)
                self._log("Auto-enabled aggressive dedup (live captions detected)")
            parent = self._source_files[0].parent
            if parent.is_dir() and not self.context_var.get().strip():
                self.context_var.set(str(parent))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Read error", str(exc))
            return
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.insert(tk.END, self._raw_text)
        self.preview_notebook.select(self.raw_text)
        if not self.title_var.get().strip():
            if len(self._source_files) == 1:
                self.title_var.set(self._source_files[0].stem.replace("_", " "))
            else:
                self.title_var.set("Combined lecture")
        n = len(self._source_files)
        self.status_var.set(f"{n} file(s) — {len(self._raw_text):,} chars combined")

    def _send_to_summarize_from_captions(self) -> None:
        self.aggressive_var.set(True)
        self._send_to_summarize()

    def _send_to_summarize(self) -> None:
        if not self._last_transcript_path or not self._last_transcript_path.is_file():
            messagebox.showinfo("Summarize", "Transcribe audio first.")
            return
        self._clear_source_files()
        self._add_paths([self._last_transcript_path], select_last=True)
        self.mode_notebook.select(self.summarize_tab)
        self.status_var.set(f"Ready to summarize — {self._last_transcript_path.name}")

    # ------------------------------------------------------------------ Logging / busy

    def _log(self, msg: str) -> None:
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _tlog(self, msg: str) -> None:
        self.transcribe_log.insert(tk.END, msg + "\n")
        self.transcribe_log.see(tk.END)

    def _cllog(self, msg: str) -> None:
        self.captions_log.insert(tk.END, msg + "\n")
        self.captions_log.see(tk.END)

    def _enable_send_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.send_summarize_btn.configure(state=state)
        self.captions_send_btn.configure(state=state)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._summarizing = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.parse_btn.configure(state=state)
        self.summarize_btn.configure(state=state)
        self.cancel_summarize_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)
        if not self._transcribing and not self._live_whisper_running:
            self.transcribe_btn.configure(state=state)
            self.snap_now_btn.configure(state=tk.DISABLED)
        if not self._captions_running:
            self.captions_start_btn.configure(state=state)
        if not self._live_whisper_running:
            self.live_start_btn.configure(state=state)

    def _cancel_summarize(self) -> None:
        if self._summarizing:
            self._summarize_cancel.set()
            self._log("Cancellation requested…")
            self.status_var.set("Cancelling summarization…")

    def _update_progress(self, current: int, total: int) -> None:
        fraction = current / max(1, total)
        if USE_CTK:
            self.progress_bar.set(fraction)
        else:
            self.progress_var.set(fraction * 100)

    # ------------------------------------------------------------------ Whisper tab

    def _sync_whisper_preset_from_model(self) -> None:
        model = self.whisper_model_var.get().strip()
        engine = self.whisper_engine_var.get()
        for label, eng, mid in WHISPER_PRESETS:
            if eng == engine and mid == model:
                self.whisper_preset_var.set(label)
                return
        self.whisper_preset_var.set("Custom model ID…")

    def _on_whisper_preset(self, _event: object = None) -> None:
        label = self.whisper_preset_var.get()
        for entry in WHISPER_PRESETS:
            if entry[0] == label:
                _, engine, model_id = entry
                self.whisper_engine_var.set(engine)
                if model_id:
                    self.whisper_model_var.set(model_id)
                return

    def _browse_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg *.webm"), ("All files", "*.*")],
        )
        if path:
            self.audio_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Output folder for notes", initialdir=self.output_var.get())
        if path:
            self.output_var.set(path)

    def _browse_context(self) -> None:
        path = filedialog.askdirectory(
            title="Context folder (prereqs, .ipynb, .md)",
            initialdir=self.context_var.get() or str(self.cfg.notes_path()),
        )
        if path:
            self.context_var.set(path)

    def _check_whisper(self) -> None:
        ok, msg = check_whisper_deps(self.whisper_engine_var.get())
        if ok:
            messagebox.showinfo("Whisper", msg)
        else:
            messagebox.showwarning("Whisper", msg)

    def _check_captions(self) -> None:
        ok, msg = check_captions_deps()
        if ok:
            messagebox.showinfo("Live Captions", msg)
        else:
            messagebox.showwarning("Live Captions", msg)

    def _run_captions_start(self) -> None:
        if self._busy or self._captions_running:
            return
        try:
            ensure_windows()
        except OSError as exc:
            messagebox.showerror("Live Captions", str(exc))
            return
        ok, msg = check_captions_deps()
        if not ok:
            messagebox.showwarning("Live Captions", msg)
            return
        self._save_settings()

        try:
            poll = max(0.1, float(self.captions_poll_var.get().strip() or "0.5"))
        except ValueError:
            poll = 0.5
        try:
            duration = max(0.0, float(self.captions_duration_var.get().strip() or "0"))
        except ValueError:
            duration = 0.0

        self._captions_stop.clear()
        self._captions_scraper = LiveCaptionsScraper(
            poll_interval=poll,
            method=self.captions_method_var.get(),
            on_segment=lambda text: self.after(0, lambda t=text: self._cllog(f"+ {t}")),
        )
        self._captions_running = True
        self.captions_start_btn.configure(state=tk.DISABLED)
        self.captions_stop_btn.configure(state=tk.NORMAL)
        self._cllog("Connecting to LiveCaptions.exe…")
        self._cllog("Enable captions with Win+Ctrl+L if needed.")
        self.status_var.set("Capturing Live Captions…")

        def work() -> None:
            try:
                max_sec = duration if duration > 0 else None
                self._captions_scraper.run(
                    max_seconds=max_sec,
                    stop_event=self._captions_stop,
                )
            except Exception as exc:
                self.after(0, lambda: self._cllog(f"Error: {exc}"))
            finally:
                self.after(0, self._finish_captions)

        threading.Thread(target=work, daemon=True).start()

    def _run_captions_stop(self) -> None:
        if not self._captions_running:
            return
        self._captions_stop.set()
        self._cllog("Stopping…")
        self.captions_stop_btn.configure(state=tk.DISABLED)

    def _finish_captions(self) -> None:
        self._captions_running = False
        self.captions_start_btn.configure(state=tk.NORMAL)
        self.captions_stop_btn.configure(state=tk.DISABLED)

        scraper = self._captions_scraper
        if not scraper or not scraper.segments:
            self._cllog("No captions captured.")
            self.status_var.set("Live Captions stopped — no text")
            return

        out_path = scraper.save(output_dir=self.cfg.transcripts_path())
        self._last_transcript_path = out_path
        self._refresh_library_list()
        self._enable_send_buttons(True)
        self._cllog(f"Saved {len(scraper.segments)} segments → {out_path}")
        self.status_var.set(f"Live Captions saved — {out_path.name}")

        if messagebox.askyesno(
            "Capture saved",
            f"Saved {len(scraper.segments)} lines to:\n{out_path}\n\n"
            "Open Summarize tab now? (Aggressive dedup will be enabled)",
        ):
            self._send_to_summarize_from_captions()

    def _live_source_label(self, value: str) -> str:
        return "Microphone" if value == "mic" else "System audio (speakers)"

    def _live_source_value(self, label: str) -> str:
        return "mic" if label.strip().lower().startswith("microphone") else "system"

    def _check_live_whisper(self) -> None:
        ok, msg = check_live_whisper_deps()
        if not ok:
            messagebox.showwarning("Live Whisper", msg)
            return
        src = self._live_source_value(self.live_source_var.get())
        if src == "system":
            sys_ok, sys_msg = check_system_audio_available()
            messagebox.showinfo("Live Whisper", f"{msg}\n\n{sys_msg}" if sys_ok else sys_msg)
        else:
            messagebox.showinfo("Live Whisper", msg)

    def _run_live_whisper_start(self) -> None:
        if self._busy or self._live_whisper_running:
            if self._summarizing:
                messagebox.showwarning(
                    "GPU busy",
                    "Summarization is running. Wait for it to finish (or cancel) before starting Whisper "
                    "to avoid GPU out-of-memory errors.",
                )
            return
        ok, msg = check_live_whisper_deps()
        if not ok:
            messagebox.showwarning("Live Whisper", msg)
            return
        audio_src = self._live_source_value(self.live_source_var.get())
        if audio_src == "system":
            sys_ok, sys_msg = check_system_audio_available()
            if not sys_ok:
                messagebox.showwarning("System audio", sys_msg)
                return
        self._save_settings()

        try:
            chunk = max(3.0, float(self.live_chunk_var.get().strip() or "10"))
        except ValueError:
            chunk = 10.0

        use_capture = self.capture_var.get()
        session: CaptureSession | None = None
        if use_capture:
            session = CaptureSession.create(self.cfg.sessions_path(), "live_whisper")
            self._capture_session = session
            session.start()
            try:
                interval = float(self.capture_interval_var.get().strip() or "0")
            except ValueError:
                interval = 0.0
            if interval > 0:
                session.start_auto_capture(interval, on_capture=lambda c: self.after(
                    0, lambda cap=c: self._tlog(f"Auto snapshot #{cap.index}")
                ))

        self._live_whisper_stop.clear()
        self._live_whisper_session = LiveWhisperSession(
            model_id=self.whisper_model_var.get().strip() or "large-v3-turbo",
            device=self.whisper_device_var.get(),
            language=self.whisper_lang_var.get().strip() or None,
            task=self.whisper_task_var.get(),
            chunk_seconds=chunk,
            audio_source=audio_src,
        )
        self._live_whisper_running = True
        self._transcribing = True
        self.live_start_btn.configure(state=tk.DISABLED)
        self.live_stop_btn.configure(state=tk.NORMAL)
        self.transcribe_btn.configure(state=tk.DISABLED)
        if use_capture:
            self.snap_now_btn.configure(state=tk.NORMAL)
        src_label = "system audio" if audio_src == "system" else "microphone"
        self._tlog(f"Live Whisper started ({src_label}) — chunk every {chunk:.0f}s")
        self.status_var.set("Live Whisper listening…")

        def on_text(text: str) -> None:
            self.after(0, lambda t=text: self._tlog(f"» {t}"))

        def on_progress(msg: str) -> None:
            self.after(0, lambda m=msg: self._tlog(m))

        def work() -> None:
            try:
                self._live_whisper_session.run(
                    stop_event=self._live_whisper_stop,
                    on_text=on_text,
                    on_progress=on_progress,
                )
            except Exception as exc:
                self.after(0, lambda: self._tlog(f"Error: {exc}"))
            finally:
                self.after(0, lambda: self._finish_live_whisper(session))

        threading.Thread(target=work, daemon=True).start()

    def _run_live_whisper_stop(self) -> None:
        if not self._live_whisper_running:
            return
        self._live_whisper_stop.set()
        self._tlog("Stopping live mic…")
        self.live_stop_btn.configure(state=tk.DISABLED)

    def _finish_live_whisper(self, capture_session: CaptureSession | None) -> None:
        self._live_whisper_running = False
        self._transcribing = False
        self.live_start_btn.configure(state=tk.NORMAL)
        self.live_stop_btn.configure(state=tk.DISABLED)
        self.transcribe_btn.configure(state=tk.NORMAL)
        self.snap_now_btn.configure(state=tk.DISABLED)
        if capture_session:
            capture_session.stop_auto_capture()

        live = self._live_whisper_session
        if not live or not live.segments:
            self._tlog("No speech transcribed.")
            self.status_var.set("Live Whisper stopped — no text")
            self._capture_session = None
            return

        text = live.full_text
        if capture_session and capture_session.captures:
            text = merge_slides_into_transcript(
                text, live.transcript_segments, capture_session.captures
            )
            capture_session.write_manifest()
            capture_session.session_dir.mkdir(parents=True, exist_ok=True)
            (capture_session.session_dir / "transcript.txt").write_text(
                text.strip() + "\n", encoding="utf-8"
            )
            self.cfg.last_session = str(capture_session.session_dir)
            save_config(self.cfg)

        out_path = save_transcript(text, output_dir=self.cfg.transcripts_path(), stem="live_whisper")
        self._last_transcript_path = out_path
        self._refresh_library_list()
        self._enable_send_buttons(True)
        self._tlog(f"Saved {len(live.segments)} chunks → {out_path}")
        self.status_var.set(f"Live Whisper saved — {out_path.name}")
        self._capture_session = None

        if messagebox.askyesno("Live Whisper saved", f"Saved to:\n{out_path}\n\nOpen Summarize tab?"):
            self._send_to_summarize()

    def _snap_now(self) -> None:
        if not self._capture_session:
            return
        try:
            cap = self._capture_session.capture_now()
            self._tlog(f"Snapshot #{cap.index} at {cap.elapsed_sec:.1f}s → {cap.path.name}")
            self.status_var.set(f"Captured slide #{cap.index}")
        except Exception as exc:
            messagebox.showerror("Screenshot failed", str(exc))

    def _set_transcribing(self, active: bool) -> None:
        self._transcribing = active
        if active and self.capture_var.get():
            self.snap_now_btn.configure(state=tk.NORMAL)
        else:
            self.snap_now_btn.configure(state=tk.DISABLED)
            if not active:
                self._capture_session = None

    def _run_transcribe(self) -> None:
        if self._busy:
            if self._summarizing:
                messagebox.showwarning(
                    "GPU busy",
                    "Summarization is running. Wait for it to finish (or cancel) before starting Whisper "
                    "to avoid GPU out-of-memory errors.",
                )
            return
        audio_raw = self.audio_var.get().strip()
        if not audio_raw:
            messagebox.showwarning("Whisper", "Select an audio file first.")
            return
        self._save_settings()

        def work() -> None:
            session: CaptureSession | None = None
            try:
                audio_path = Path(audio_raw)
                use_capture = self.capture_var.get()

                def on_progress(msg: str) -> None:
                    self.after(0, lambda m=msg: self._tlog(m))

                if use_capture:
                    session = CaptureSession.create(self.cfg.sessions_path(), audio_path.stem)
                    self.after(0, lambda: setattr(self, "_capture_session", session))
                    session.start()
                    try:
                        interval = float(self.capture_interval_var.get().strip() or "0")
                    except ValueError:
                        interval = 0.0

                    def on_cap(cap) -> None:
                        self.after(0, lambda c=cap: self._tlog(f"Auto snapshot #{c.index} at {c.elapsed_sec:.1f}s"))

                    if interval > 0:
                        session.start_auto_capture(interval, on_capture=on_cap)
                        self.after(0, lambda: self._tlog(f"Auto-capture every {interval}s"))

                self.after(0, lambda: self._set_transcribing(True))

                result = transcribe_audio(
                    audio_path,
                    engine=self.whisper_engine_var.get(),
                    model_id=self.whisper_model_var.get().strip(),
                    device=self.whisper_device_var.get(),
                    language=self.whisper_lang_var.get().strip() or None,
                    task=self.whisper_task_var.get(),
                    on_progress=on_progress,
                )

                text = result.text
                if session:
                    text = merge_slides_into_transcript(text, result.segments, session.captures)
                    if session.captures:
                        session.write_manifest()
                    session_transcript = session.session_dir / "transcript.txt"
                    session_transcript.write_text(text.strip() + "\n", encoding="utf-8")
                    self.cfg.last_session = str(session.session_dir)
                    save_config(self.cfg)

                out_path = save_transcript(text, output_dir=self.cfg.transcripts_path(), stem=audio_path.stem)
                self._last_transcript_path = out_path

                def done() -> None:
                    self._refresh_library_list()
                    self._enable_send_buttons(True)
                    self._tlog(f"Saved: {out_path}")
                    if session:
                        self._tlog(f"Session: {session.session_dir} ({len(session.captures)} snapshots)")
                    self.status_var.set(f"Transcribed — {out_path.name}")
                    if messagebox.askyesno(
                        "Transcribe done",
                        f"Saved to:\n{out_path}\n\nOpen Summarize tab now?",
                    ):
                        self._send_to_summarize()

                self.after(0, done)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Transcribe failed", str(exc)))
            finally:
                if session:
                    session.stop_auto_capture()
                self.after(0, lambda: self._set_transcribing(False))
                self.after(0, lambda: self._set_busy(False))

        self._set_busy(True)
        self._tlog("Starting Whisper…")
        self.status_var.set("Transcribing…")
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ Summarize tab

    def _resolve_sources(self) -> list[Path]:
        if not self._source_files:
            raise FileNotFoundError("Add at least one transcript file (Add file(s) or From library).")
        for p in self._source_files:
            if not p.is_file():
                raise FileNotFoundError(f"Not found: {p}")
        return list(self._source_files)

    def _run_parse(self) -> None:
        if self._busy:
            return
        try:
            paths = self._resolve_sources()
            if not self._raw_text:
                self._load_combined_preview()
            transcript_text, _, _ = prepare_sources(paths)
            aggressive = self.aggressive_var.get()
            self._cleaned_text = parse_transcript(transcript_text, aggressive=aggressive)
            self.clean_text.delete("1.0", tk.END)
            self.clean_text.insert(tk.END, self._cleaned_text)
            self.preview_notebook.select(self.clean_text)
            label = paths[0].name if len(paths) == 1 else f"{len(paths)} files combined"
            words = len(self._cleaned_text.split())
            self._log(f"Parsed {label}: {words:,} words after cleanup")
            self.status_var.set(f"Cleaned — {words:,} words")
        except Exception as exc:
            messagebox.showerror("Parse failed", str(exc))

    def _run_summarize(self) -> None:
        if self._busy:
            return
        if self._transcribing or self._live_whisper_running:
            messagebox.showwarning(
                "GPU busy",
                "Stop Whisper transcription before summarizing to avoid GPU out-of-memory errors.",
            )
            return
        self._save_settings()
        self._summarize_cancel.clear()

        def work() -> None:
            try:
                paths = self._resolve_sources()
                title = self.title_var.get().strip() or (
                    paths[0].stem.replace("_", " ") if len(paths) == 1 else "Combined lecture"
                )
                out = Path(self.output_var.get().strip()) if self.output_var.get().strip() else None
                opts = options_from_config(self.cfg)
                context = self.context_var.get().strip() or None
                if not context and len(paths) > 1:
                    context = str(paths[0].parent)
                session_dir = None
                if self.cfg.last_session and Path(self.cfg.last_session).is_dir():
                    session_dir = Path(self.cfg.last_session)
                for p in paths:
                    if (p.parent / "snapshots").is_dir():
                        session_dir = p.parent
                        break

                def on_progress(msg: str) -> None:
                    self.after(0, lambda m=msg: self._log(m))

                def on_step(current: int, total: int, msg: str) -> None:
                    self.after(0, lambda c=current, t=total: self._update_progress(c, t))

                note_path, body = generate_notes_from_files(
                    paths,
                    title=title,
                    aggressive=self.aggressive_var.get(),
                    output_dir=out,
                    opts=opts,
                    context_folder=context,
                    refine_second_pass=self.refine_var.get() and not self.fast_var.get(),
                    enrich_with_references=self.enrich_var.get() and not self.fast_var.get(),
                    fast_mode=self.fast_var.get(),
                    session_dir=session_dir,
                    on_progress=on_progress,
                    on_step=on_step,
                    cancel_event=self._summarize_cancel.is_set,
                )

                def done() -> None:
                    self.clean_text.delete("1.0", tk.END)
                    self.clean_text.insert(tk.END, body)
                    self.preview_notebook.select(self.clean_text)
                    self._log(f"Saved: {note_path}")
                    self.status_var.set(f"Notes saved — {note_path.name}")
                    self._update_progress(1, 1)
                    messagebox.showinfo("Done", f"Notes saved to:\n{note_path}")

                self.after(0, done)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Summarize failed", str(exc)))
            finally:
                def reset_ui() -> None:
                    self._set_busy(False)
                    self._update_progress(0, 1)

                self.after(0, reset_ui)

        self._set_busy(True)
        self._update_progress(0, 1)
        self._log("Starting summarization…")
        self.status_var.set("Summarizing…")
        threading.Thread(target=work, daemon=True).start()

    def _test_llm(self) -> None:
        self._save_settings()
        self.cfg = load_config()
        if llm_reachable(options_from_config(self.cfg)):
            messagebox.showinfo("LLM", "Connection OK")
            self.status_var.set("LLM reachable")
        else:
            messagebox.showwarning("LLM", "Could not reach the LLM. Start Ollama or LM Studio.")

    def _open_output(self) -> None:
        folder = Path(self.output_var.get().strip() or str(self.cfg.notes_path()))
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = TranscriptStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
