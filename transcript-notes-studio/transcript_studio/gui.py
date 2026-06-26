"""Tkinter GUI — Summarize (browse & combine) and Transcribe (separate) workflows."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import customtkinter as ctk

    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")
    USE_CTK = True
except ImportError:
    USE_CTK = False
    ctk = None  # type: ignore[misc, assignment]

# Shared light palette (ttk + CTk + classic tk widgets)
_UI_BG = "#f3f4f6"
_UI_PANEL = "#ffffff"
_UI_BORDER = "#d1d5db"
_UI_TEXT = "#1f2937"
_UI_MUTED = "#6b7280"
_UI_ACCENT = "#2563eb"
_UI_ACCENT_HOVER = "#1d4ed8"

from transcript_studio.config import load_config, save_config
from transcript_studio.llm_client import llm_reachable, options_from_config
from transcript_studio.ui_text import (
    format_preview_text,
    insert_text_chunked,
    parse_chunk_progress,
    preview_wrap_mode,
)
from transcript_studio.notes_generator import (
    combine_source_files,
    generate_notes_from_files,
    generate_notes_from_text,
    list_transcripts,
    parse_transcript,
    resolve_session_snapshots_dir,
)
from transcript_studio.parse_throttle import (
    format_parse_estimate,
    speed_to_throttle,
    throttle_labels,
)
from transcript_studio.parse_audit import (
    audit_notes,
    audit_parse,
    format_audit_report,
    format_notes_audit_report,
)
from transcript_studio.log_setup import log_error, log_file_path, setup_logging, tail_log
from transcript_studio.export_insights import export_run_insights
from transcript_studio.quality_presets import apply_quality_preset
from transcript_studio.system_sensors import format_system_line, try_cpu_load_pct, try_cpu_temp_celsius
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


def _configure_app_style(root: tk.Misc) -> None:
    """Unify ttk/tk colors so LabelFrames and tabs don't render as harsh black bars."""
    if USE_CTK and isinstance(root, ctk.CTk):
        root.configure(fg_color=(_UI_BG, _UI_BG))

    for pattern, value in (
        ("*Background", _UI_BG),
        ("*Listbox*Background", _UI_PANEL),
        ("*Listbox*Foreground", _UI_TEXT),
        ("*Listbox*selectBackground", _UI_ACCENT),
        ("*Listbox*selectForeground", "#ffffff"),
        ("*Text*Background", _UI_PANEL),
        ("*Text*Foreground", _UI_TEXT),
        ("*Text*insertBackground", _UI_TEXT),
    ):
        root.option_add(pattern, value)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=_UI_BG, foreground=_UI_TEXT, fieldbackground=_UI_PANEL)
    style.configure("TFrame", background=_UI_BG)
    style.configure("TLabel", background=_UI_BG, foreground=_UI_TEXT)
    style.configure(
        "TLabelframe",
        background=_UI_BG,
        bordercolor=_UI_BORDER,
        relief="groove",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=_UI_BG,
        foreground=_UI_MUTED,
        font=("Segoe UI", 9, "bold"),
    )
    style.configure("TNotebook", background=_UI_BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background="#e5e7eb",
        foreground=_UI_TEXT,
        padding=(12, 6),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", _UI_PANEL)],
        foreground=[("selected", _UI_TEXT)],
    )
    style.configure(
        "TButton",
        background="#e5e7eb",
        foreground=_UI_TEXT,
        bordercolor=_UI_BORDER,
        focusthickness=1,
        focuscolor=_UI_ACCENT,
        padding=(10, 4),
    )
    style.map("TButton", background=[("active", "#dbeafe"), ("pressed", "#bfdbfe")])
    style.configure("TEntry", fieldbackground=_UI_PANEL, foreground=_UI_TEXT, bordercolor=_UI_BORDER)
    style.configure("TCombobox", fieldbackground=_UI_PANEL, foreground=_UI_TEXT, bordercolor=_UI_BORDER)
    style.configure("TCheckbutton", background=_UI_BG, foreground=_UI_TEXT)
    style.configure("Horizontal.TProgressbar", background=_UI_ACCENT, troughcolor="#e5e7eb", borderwidth=0)


def _apply_windows_title_bar(window: tk.Misc) -> None:
    """Use a neutral light title bar instead of the Windows accent color."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if hwnd == 0:
            hwnd = window.winfo_id()
        caption_color = 0x00F3F4F6  # #f3f4f6 in BGR
        text_color = 0x0037291F  # #1f2937 in BGR
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(caption_color)), 4)
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(text_color)), 4)
    except Exception:
        pass


class TranscriptStudioApp(_AppBase):
    def __init__(self) -> None:
        super().__init__()
        self.title("Transcript Notes Studio")
        self.minsize(900, 640)
        self.geometry("1000x720")

        self.cfg = load_config()
        self._raw_text = ""
        self._cleaned_text = ""
        self._last_cleaned_path: Path | None = None
        self._last_notes_audit: str = ""
        self._last_cleanup_audit: str = ""
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
        self._last_note_path: Path | None = None
        self._workflow_step = 0
        self._step_frames: dict[str, ttk.Frame] = {}

        _configure_app_style(self)
        self._build_ui()
        self._refresh_library_list()
        self._load_fields_from_config()
        self._refresh_llm_status()
        self._refresh_system_status()
        self.after(45_000, self._schedule_system_status)
        self.after(50, lambda: _apply_windows_title_bar(self))

    # ------------------------------------------------------------------ UI shell

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        self._build_header(outer)
        self._build_global_progress(outer)

        body = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        rail = ttk.Frame(body, width=180, padding=(0, 4))
        body.add(rail, weight=0)
        self._build_workflow_rail(rail)

        main_col = ttk.Frame(body, padding=(8, 0))
        body.add(main_col, weight=1)

        self._step_frames["capture"] = ttk.Frame(main_col)
        self._step_frames["tune"] = ttk.Frame(main_col)
        self._step_frames["generate"] = ttk.Frame(main_col)
        self._step_frames["done"] = ttk.Frame(main_col)

        self._build_capture_step(self._step_frames["capture"])
        self._build_tune_step(self._step_frames["tune"])
        self._build_generate_step(self._step_frames["generate"])
        self._build_done_step(self._step_frames["done"])

        log_frame = ttk.LabelFrame(outer, text="Log", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(8, 0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 9), height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Ready — Capture → Tune → Generate → Done")
        ttk.Label(outer, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, pady=(6, 0)
        )

        self._show_workflow_step(0)

    def _build_header(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Transcript Notes Studio", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        self.llm_status_var = tk.StringVar(value="LLM: checking…")
        ttk.Label(bar, textvariable=self.llm_status_var, foreground=_UI_MUTED).pack(side=tk.LEFT, padx=(16, 0))
        self.system_status_var = tk.StringVar(value="System: …")
        ttk.Label(bar, textvariable=self.system_status_var, foreground=_UI_MUTED).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(bar, text="Open log", command=self._open_log_file).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(bar, text="Test LLM", command=self._test_llm).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(bar, text="Settings", command=self._save_settings).pack(side=tk.RIGHT)

    def _build_global_progress(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(6, 0))
        self.progress_status_var = tk.StringVar(value="")
        ttk.Label(row, textvariable=self.progress_status_var, width=28).pack(side=tk.LEFT, anchor=tk.W)
        self.global_progress = ttk.Progressbar(row, mode="determinate", maximum=100)
        self.global_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    def _progress_begin(self, message: str, *, indeterminate: bool = False) -> None:
        self.progress_status_var.set(message)
        self.global_progress.stop()
        if indeterminate:
            self.global_progress.configure(mode="indeterminate", maximum=100)
            self.global_progress.start(10)
        else:
            self.global_progress.configure(mode="determinate", maximum=100, value=0)

    def _progress_update(self, fraction: float, message: str | None = None) -> None:
        self.global_progress.stop()
        self.global_progress.configure(mode="determinate", maximum=100)
        self.global_progress["value"] = max(0.0, min(1.0, fraction)) * 100
        if message:
            self.progress_status_var.set(message)

    def _progress_steps(self, current: int, total: int, message: str = "") -> None:
        if total > 0:
            self._progress_update(current / total, message or f"Step {current}/{total}")

    def _progress_end(self) -> None:
        self.global_progress.stop()
        self.global_progress.configure(mode="determinate", value=0)
        self.progress_status_var.set("")

    def _set_preview_text(self, widget: scrolledtext.ScrolledText, full_text: str) -> None:
        """Show a truncated, scroll-friendly preview without blocking the UI."""
        display, truncated = format_preview_text(full_text)
        widget.configure(wrap=preview_wrap_mode(display))

        def on_done() -> None:
            if truncated:
                self.status_var.set(f"Preview truncated — {len(full_text):,} chars total")

        insert_text_chunked(widget, display, schedule=self.after, on_complete=on_done)

    def _build_workflow_rail(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Workflow", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))
        self._step_buttons: list[ttk.Button] = []
        for index, label in enumerate(("1 Capture", "2 Tune", "3 Generate", "4 Done")):
            btn = ttk.Button(parent, text=label, command=lambda i=index: self._show_workflow_step(i))
            btn.pack(fill=tk.X, pady=2)
            self._step_buttons.append(btn)

        help = ttk.LabelFrame(parent, text="Features", padding=6)
        help.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        help_text = (
            "Live Captions — Win+Ctrl+L → data/transcripts/\n"
            "Parse — collapse caption prefix growth\n"
            "Generate — LLM chunks + mermaid rules\n"
            "Context — PDF/ipynb/md references\n"
            "Whisper — when captions unavailable\n"
            "Quality preset — slow CPU OK\n"
            "Docs: docs/LOCAL_LLM_NOTES_GUIDE.md\n\n"
            f"Transcripts: {self.cfg.transcripts_path()}\n"
            f"Notes: {self.cfg.notes_path()}\n"
            f"Error log: {log_file_path()}"
        )
        ttk.Label(help, text=help_text, wraplength=160, justify=tk.LEFT, font=("Segoe UI", 8)).pack(anchor=tk.W)

    def _show_workflow_step(self, index: int) -> None:
        self._workflow_step = index
        keys = ("capture", "tune", "generate", "done")
        for i, key in enumerate(keys):
            frame = self._step_frames[key]
            if i == index:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
            style = "Accent.TButton" if i == index else "TButton"
            try:
                self._step_buttons[i].configure(style=style)
            except tk.TclError:
                pass

    def _build_capture_step(self, parent: ttk.Frame) -> None:
        intro = ttk.Label(
            parent,
            text="Capture lecture audio or Windows Live Captions. Saved transcripts go to data/transcripts/.",
            wraplength=760,
        )
        intro.pack(anchor=tk.W, pady=(0, 8))

        self.capture_notebook = ttk.Notebook(parent)
        self.capture_notebook.pack(fill=tk.BOTH, expand=True)

        self.captions_tab = ttk.Frame(self.capture_notebook, padding=4)
        self.transcribe_tab = ttk.Frame(self.capture_notebook, padding=4)
        self.capture_notebook.add(self.captions_tab, text="  Live Captions  ")
        self.capture_notebook.add(self.transcribe_tab, text="  Whisper  ")

        self._build_captions_tab()
        self._build_transcribe_tab()

        nav = ttk.Frame(parent)
        nav.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(nav, text="Next: Tune transcript →", command=lambda: self._show_workflow_step(1)).pack(side=tk.RIGHT)

    def _build_tune_step(self, parent: ttk.Frame) -> None:
        self._build_summarize_sources(parent)

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.parse_btn = self._add_button(actions, "Parse & preview", self._run_parse)
        self.parse_btn.pack(side=tk.LEFT)
        self.save_cleaned_btn = ttk.Button(
            actions, text="Save cleaned…", command=self._save_cleaned_transcript, state=tk.DISABLED
        )
        self.save_cleaned_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.parse_stats_var = tk.StringVar(value="Parse to see char / word counts")
        ttk.Label(actions, textvariable=self.parse_stats_var, foreground=_UI_MUTED).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        ttk.Button(actions, text="← Capture", command=lambda: self._show_workflow_step(0)).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(actions, text="Next: Generate →", command=lambda: self._show_workflow_step(2)).pack(side=tk.RIGHT)

        self.preview_notebook = ttk.Notebook(parent)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True)

        self.raw_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        self.clean_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        self.audit_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        self.notes_audit_text = scrolledtext.ScrolledText(self.preview_notebook, wrap=tk.WORD, font=("Consolas", 10))
        for widget in (self.raw_text, self.clean_text, self.audit_text, self.notes_audit_text):
            widget.configure(state=tk.DISABLED)
        self.preview_notebook.add(self.raw_text, text="Combined raw")
        self.preview_notebook.add(self.clean_text, text="Cleaned preview")
        self.preview_notebook.add(self.audit_text, text="Cleanup audit")
        self.preview_notebook.add(self.notes_audit_text, text="Notes audit")

    def _build_generate_step(self, parent: ttk.Frame) -> None:
        self._build_summarize_options(parent)

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X, pady=(0, 6))
        self.summarize_btn = self._add_button(actions, "Generate notes", self._run_summarize)
        self.summarize_btn.pack(side=tk.LEFT)
        self.cancel_summarize_btn = self._add_button(actions, "Cancel", self._cancel_summarize)
        self.cancel_summarize_btn.configure(state=tk.DISABLED)
        self.cancel_summarize_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._add_button(actions, "Open output folder", self._open_output).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="← Tune", command=lambda: self._show_workflow_step(1)).pack(side=tk.RIGHT)

    def _build_done_step(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="Notes are saved under data/notes/. Open them in the web Study Library for reading, mermaid repair, and quiz.",
            wraplength=760,
        ).pack(anchor=tk.W, pady=(0, 12))

        paths = ttk.LabelFrame(parent, text="Last run", padding=8)
        paths.pack(fill=tk.X, pady=(0, 8))
        self.done_transcript_var = tk.StringVar(value="(none)")
        self.done_note_var = tk.StringVar(value="(none)")
        ttk.Label(paths, text="Transcript:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(paths, textvariable=self.done_transcript_var, wraplength=600).grid(row=0, column=1, sticky=tk.W, padx=(8, 0))
        ttk.Label(paths, text="Note:").grid(row=1, column=0, sticky=tk.W, pady=(4, 0))
        ttk.Label(paths, textvariable=self.done_note_var, wraplength=600).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=(4, 0))

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="Open notes folder", command=self._open_output).pack(side=tk.LEFT)
        ttk.Button(actions, text="Open Study Library in browser", command=self._open_study_library).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Export insights…", command=self._export_run_insights).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Start new lecture", command=lambda: self._show_workflow_step(0)).pack(side=tk.LEFT, padx=(8, 0))

    def _refresh_llm_status(self) -> None:
        def check() -> None:
            ok = llm_reachable(options_from_config(self.cfg))
            model = self.cfg.llm_model
            status = f"LLM: {'● reachable' if ok else '○ offline'} — {model}"
            self.after(0, lambda: self.llm_status_var.set(status))

        threading.Thread(target=check, daemon=True).start()

    def _refresh_system_status(self) -> None:
        def check() -> None:
            line = format_system_line(
                temp_c=try_cpu_temp_celsius(),
                load_pct=try_cpu_load_pct(),
            )
            self.after(0, lambda: self.system_status_var.set(line))

        threading.Thread(target=check, daemon=True).start()

    def _schedule_system_status(self) -> None:
        self._refresh_system_status()
        self.after(45_000, self._schedule_system_status)

    def _apply_quality_from_preset(self) -> None:
        name = self.quality_var.get().strip().lower() or "balanced"
        preset = apply_quality_preset(name)
        self.fast_var.set(bool(preset["fast_mode"]))
        self.legacy_pipeline_var.set(bool(preset["legacy_notes_pipeline"]))
        self.semantic_chunk_var.set(bool(preset["use_semantic_chunking"]))
        self.refine_var.set(bool(preset["refine_second_pass"]))
        self.parse_speed_var.set(int(preset["parse_speed"]))
        self.cfg.notes_quality = name
        self.cfg.max_llm_chunks = int(preset["max_llm_chunks"])
        self.cfg.llm_pause_sec = float(preset["llm_pause_sec"])
        self._refresh_parse_estimate()

    def _export_run_insights(self) -> None:
        folder = filedialog.askdirectory(
            title="Export run insights folder",
            initialdir=str(self.cfg.notes_path()),
        )
        if not folder:
            return
        try:
            path = export_run_insights(
                Path(folder),
                note_path=self._last_note_path,
                transcript_path=self._source_files[0] if self._source_files else None,
                cleaned_text=self._cleaned_text,
                cleanup_audit=self._last_cleanup_audit,
                notes_audit=self._last_notes_audit,
                cfg=self.cfg,
            )
            messagebox.showinfo("Exported", f"Insights saved to:\n{path}")
            self._log(f"Exported insights -> {path}")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
        self.after(30_000, self._refresh_llm_status)

    def _open_log_file(self) -> None:
        path = log_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text("", encoding="utf-8")
        self._log(f"Log file: {path}")
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])

    def _open_study_library(self) -> None:
        import webbrowser

        webbrowser.open("http://localhost:5173/lecture-notes")

    def _update_done_paths(self) -> None:
        if self._last_transcript_path:
            self.done_transcript_var.set(str(self._last_transcript_path))
        if self._last_note_path:
            self.done_note_var.set(str(self._last_note_path))

    def _build_summarize_sources(self, tab: ttk.Frame) -> None:

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

        dedup_row = ttk.Frame(tab)
        dedup_row.pack(fill=tk.X, pady=(6, 0))
        self.aggressive_var = tk.BooleanVar(value=self.cfg.aggressive_dedup_default)
        self._add_checkbox(
            dedup_row, "Aggressive dedup (Live Captions prefix growth)", self.aggressive_var,
            command=self._refresh_parse_estimate,
        ).pack(side=tk.LEFT)
        self.thorough_parse_var = tk.BooleanVar(value=self.cfg.thorough_parse)
        self._add_checkbox(
            dedup_row,
            "Thorough parse (multi-pass)",
            self.thorough_parse_var,
            command=self._refresh_parse_estimate,
        ).pack(side=tk.LEFT, padx=(12, 0))

        speed_row = ttk.Frame(tab)
        speed_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(speed_row, text="Parse speed (CPU)").pack(anchor=tk.W)
        speed_ctrl = ttk.Frame(speed_row)
        speed_ctrl.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(speed_ctrl, text="Fast / hot", foreground=_UI_MUTED).pack(side=tk.LEFT)
        self.parse_speed_var = tk.IntVar(value=self.cfg.parse_speed)
        self.parse_speed_scale = ttk.Scale(
            speed_ctrl,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.parse_speed_var,
            command=self._on_parse_speed_slider,
        )
        self.parse_speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Label(speed_ctrl, text="Cool / slow", foreground=_UI_MUTED).pack(side=tk.LEFT)
        self.parse_estimate_var = tk.StringVar(value="Select a source to see time & CPU estimate")
        ttk.Label(
            speed_row,
            textvariable=self.parse_estimate_var,
            wraplength=720,
            foreground=_UI_MUTED,
        ).pack(anchor=tk.W, pady=(4, 0))

    def _build_summarize_options(self, tab: ttk.Frame) -> None:
        opts = ttk.LabelFrame(tab, text="Notes output & options", padding=8)
        opts.pack(fill=tk.X, pady=(0, 6))

        r0 = ttk.Frame(opts)
        r0.pack(fill=tk.X)
        ttk.Label(r0, text="Quality preset").pack(side=tk.LEFT)
        self.quality_var = tk.StringVar(value=getattr(self.cfg, "notes_quality", "balanced"))
        ttk.Combobox(
            r0,
            textvariable=self.quality_var,
            values=["fast", "balanced", "quality"],
            width=12,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(
            r0,
            text="quality = more LLM passes + pauses (CPU-friendly, slower). LM Studio: GPU layers 0 for CPU-only.",
            foreground=_UI_MUTED,
            wraplength=520,
        ).pack(side=tk.LEFT)

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

        r3 = ttk.Frame(opts)
        r3.pack(fill=tk.X, pady=(6, 0))
        self.legacy_pipeline_var = tk.BooleanVar(value=self.cfg.legacy_notes_pipeline)
        self.fast_var = tk.BooleanVar(value=self.cfg.fast_mode)
        self.refine_var = tk.BooleanVar(value=self.cfg.refine_second_pass)
        self.semantic_chunk_var = tk.BooleanVar(value=self.cfg.use_semantic_chunking)
        self.tags_var = tk.BooleanVar(value=self.cfg.use_tag_extraction)
        self.wikilinks_var = tk.BooleanVar(value=self.cfg.inject_wikilinks)
        self._add_checkbox(
            r3,
            "Legacy pipeline (run_transcript_to_notes.bat style)",
            self.legacy_pipeline_var,
            command=self._on_legacy_pipeline_toggle,
        ).pack(side=tk.LEFT)
        self._add_checkbox(r3, "Fast mode (chunk pass only)", self.fast_var).pack(side=tk.LEFT, padx=(12, 0))
        self._add_checkbox(r3, "2nd-pass refine", self.refine_var).pack(side=tk.LEFT, padx=(12, 0))
        self._add_checkbox(r3, "Semantic chunking", self.semantic_chunk_var).pack(side=tk.LEFT, padx=(12, 0))

        r4 = ttk.Frame(opts)
        r4.pack(fill=tk.X, pady=(6, 0))
        self._add_checkbox(r4, "Tag extraction", self.tags_var).pack(side=tk.LEFT)
        self._add_checkbox(r4, "Inject wikilinks", self.wikilinks_var).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(
            r4,
            text="Wikilinks only appear if other .md notes in the same folder share headings (often none).",
            foreground=_UI_MUTED,
        ).pack(side=tk.RIGHT)

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

    def _add_checkbox(self, parent, text: str, variable: tk.BooleanVar, *, command=None):
        if USE_CTK:
            kwargs = dict(
                text=text,
                variable=variable,
                fg_color=_UI_ACCENT,
                hover_color=_UI_ACCENT_HOVER,
                text_color=_UI_TEXT,
                border_color=_UI_BORDER,
            )
            if command is not None:
                kwargs["command"] = command
            return ctk.CTkCheckBox(parent, **kwargs)
        return ttk.Checkbutton(parent, text=text, variable=variable, command=command)

    def _add_button(self, parent, text: str, command):
        if USE_CTK:
            return ctk.CTkButton(
                parent,
                text=text,
                command=command,
                fg_color=_UI_ACCENT,
                hover_color=_UI_ACCENT_HOVER,
                text_color="#ffffff",
                corner_radius=6,
            )
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

    # ------------------------------------------------------------------ Config

    def _load_fields_from_config(self) -> None:
        self.provider_var.set(self.cfg.llm_provider)
        self.url_var.set(self.cfg.llm_base_url)
        self.model_var.set(self.cfg.llm_model)
        self.output_var.set(str(self.cfg.notes_path()))
        self.quality_var.set(getattr(self.cfg, "notes_quality", "balanced"))
        self.legacy_pipeline_var.set(self.cfg.legacy_notes_pipeline)
        self.fast_var.set(self.cfg.fast_mode)
        self.refine_var.set(self.cfg.refine_second_pass)
        self.semantic_chunk_var.set(self.cfg.use_semantic_chunking)
        self.tags_var.set(self.cfg.use_tag_extraction)
        self.wikilinks_var.set(self.cfg.inject_wikilinks)
        self.temp_var.set(str(self.cfg.llm_temperature))
        self.aggressive_var.set(self.cfg.aggressive_dedup_default)
        self.thorough_parse_var.set(self.cfg.thorough_parse)
        self.parse_speed_var.set(self.cfg.parse_speed)
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
        self.cfg.thorough_parse = self.thorough_parse_var.get()
        self.cfg.parse_speed = int(round(self.parse_speed_var.get()))
        self.cfg.legacy_notes_pipeline = self.legacy_pipeline_var.get()
        self.cfg.notes_quality = self.quality_var.get().strip().lower() or "balanced"
        self.cfg.fast_mode = self.fast_var.get()
        self.cfg.refine_second_pass = self.refine_var.get()
        self.cfg.use_semantic_chunking = self.semantic_chunk_var.get()
        self.cfg.use_tag_extraction = self.tags_var.get()
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
        self._cleaned_text = ""
        self.raw_text.configure(state=tk.NORMAL)
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.configure(state=tk.DISABLED)
        self.parse_stats_var.set("Parse to see char / word counts")
        try:
            self.save_cleaned_btn.configure(state=tk.DISABLED)
        except tk.TclError:
            pass
        self.status_var.set("Source list cleared")

    def _on_source_select(self, _event: object) -> None:
        if self._source_files:
            self._load_combined_preview()

    def _load_combined_preview(self) -> None:
        if not self._source_files:
            return
        paths = list(self._source_files)
        self._progress_begin("Loading sources…", indeterminate=True)

        def work() -> None:
            try:
                transcript_text, reference_text, auto_aggressive, _manifest = prepare_sources(paths)
                raw = transcript_text
                if reference_text:
                    raw += (
                        f"\n\n--- Reference materials ({len(reference_text):,} chars, not parsed as transcript) ---\n\n"
                        + reference_text[:8000]
                    )
                    if len(reference_text) > 8000:
                        raw += "\n\n… [reference preview truncated]"
                self.after(
                    0,
                    lambda: self._apply_combined_preview(paths, raw, auto_aggressive),
                )
            except (OSError, ValueError) as exc:
                self.after(0, lambda: messagebox.showerror("Read error", str(exc)))
            finally:
                self.after(0, self._progress_end)

        threading.Thread(target=work, daemon=True).start()

    def _apply_combined_preview(self, paths: list[Path], raw: str, auto_aggressive: bool) -> None:
        self._raw_text = raw
        self._set_preview_text(self.raw_text, self._raw_text)
        self.preview_notebook.select(self.raw_text)
        if auto_aggressive and not self.aggressive_var.get():
            self.aggressive_var.set(True)
            self._log("Auto-enabled aggressive dedup (live captions detected)")
        parent = paths[0].parent
        if parent.is_dir() and not self.context_var.get().strip():
            if self._is_sensible_context_folder(parent):
                self.context_var.set(str(parent))
        if not self.title_var.get().strip():
            if len(paths) == 1:
                self.title_var.set(paths[0].stem.replace("_", " "))
            else:
                self.title_var.set("Combined lecture")
        n = len(paths)
        self.status_var.set(f"{n} file(s) — {len(self._raw_text):,} chars combined")
        self._refresh_parse_estimate()

    def _parse_line_count(self) -> int:
        if self._raw_text:
            return max(1, self._raw_text.count("\n") + 1)
        return 0

    def _on_parse_speed_slider(self, _value: str = "") -> None:
        self._refresh_parse_estimate()

    def _refresh_parse_estimate(self, temp_c: float | None = None) -> None:
        lines = self._parse_line_count()
        if lines < 1:
            self.parse_estimate_var.set("Select a source to see time & CPU estimate")
            return
        speed = int(round(self.parse_speed_var.get()))
        thorough = self.thorough_parse_var.get()
        aggressive = self.aggressive_var.get()
        if temp_c is None:
            self.parse_estimate_var.set(
                format_parse_estimate(
                    lines,
                    speed,
                    thorough=thorough,
                    aggressive=aggressive,
                    temp_c=None,
                )
            )

            def fetch_temp() -> None:
                temp = try_cpu_temp_celsius()
                if temp is not None:
                    self._ui(
                        lambda: self.parse_estimate_var.set(
                            format_parse_estimate(
                                lines,
                                speed,
                                thorough=thorough,
                                aggressive=aggressive,
                                temp_c=temp,
                            )
                        )
                    )

            threading.Thread(target=fetch_temp, daemon=True).start()
            return
        self.parse_estimate_var.set(
            format_parse_estimate(
                lines,
                speed,
                thorough=thorough,
                aggressive=aggressive,
                temp_c=temp_c,
            )
        )

    def _on_legacy_pipeline_toggle(self) -> None:
        if self.legacy_pipeline_var.get():
            self.fast_var.set(True)
            self.refine_var.set(False)
            self.semantic_chunk_var.set(False)
            self.wikilinks_var.set(False)
            self.tags_var.set(False)

    def _pre_cleaned_for_generate(self) -> str | None:
        text = (self._cleaned_text or "").strip()
        return text or None

    def _is_sensible_context_folder(self, folder: Path) -> bool:
        """Avoid pointing context at the whole transcripts library (causes OOM)."""
        try:
            if folder.resolve() == self.cfg.transcripts_path().resolve():
                return False
        except OSError:
            return False
        ref_ext = {".pdf", ".ipynb", ".md"}
        return any(folder.glob(f"*{ext}") for ext in ref_ext) or any(
            folder.rglob(f"*{ext}") for ext in ref_ext
        )

    def _sanitize_context_folder(self, context: str | None) -> str | None:
        if not context:
            return None
        path = Path(context).expanduser()
        if not path.is_dir():
            return context
        try:
            if path.resolve() == self.cfg.transcripts_path().resolve():
                self._log("Skipped context folder — use PDF/Colab folder, not data/transcripts/")
                return None
        except OSError:
            pass
        return context

    def _ui_alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _ui(self, callback) -> None:
        """Schedule a UI callback only if the window still exists."""
        if self._ui_alive():
            self.after(0, callback)

    def _send_to_summarize_from_captions(self) -> None:
        self.aggressive_var.set(True)
        self._send_to_summarize()

    def _send_to_summarize(self) -> None:
        if not self._last_transcript_path or not self._last_transcript_path.is_file():
            messagebox.showinfo("Summarize", "Transcribe audio first.")
            return
        self._clear_source_files()
        self._add_paths([self._last_transcript_path], select_last=True)
        self._show_workflow_step(1)
        self.status_var.set(f"Ready to tune — {self._last_transcript_path.name}")

    # ------------------------------------------------------------------ Logging / busy

    def _log(self, msg: str) -> None:
        self.log_text.insert(tk.END, msg + "\n")
        try:
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > 400:
                self.log_text.delete("1.0", f"{line_count - 400}.0")
        except (tk.TclError, ValueError):
            pass
        self.log_text.see(tk.END)

    def _on_operation_progress(self, msg: str) -> None:
        """Route backend progress messages to log + global progress bar."""
        self._log(msg)
        chunk = parse_chunk_progress(msg)
        if chunk:
            current, total = chunk
            self._progress_steps(current, total, msg)
        elif "Refining" in msg or "Injecting" in msg or "Embedding" in msg:
            self._progress_update(0.92, msg)
        elif msg.startswith("Done"):
            self._progress_update(1.0, msg)

    def _tlog(self, msg: str) -> None:
        self._on_operation_progress(msg)

    def _cllog(self, msg: str) -> None:
        self._on_operation_progress(msg)

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
        self._progress_steps(current, total)

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
        self._caption_segment_count = 0
        self._captions_scraper = LiveCaptionsScraper(
            poll_interval=poll,
            method=self.captions_method_var.get(),
            on_segment=lambda text: self.after(0, lambda t=text: self._captions_segment(t)),
        )
        self._captions_running = True
        self.captions_start_btn.configure(state=tk.DISABLED)
        self.captions_stop_btn.configure(state=tk.NORMAL)
        self._progress_begin("Capturing Live Captions…", indeterminate=True)
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
                err = f"{type(exc).__name__}: {exc}"
                self.after(0, lambda msg=err: self._cllog(f"Error: {msg}"))
            finally:
                self.after(0, self._finish_captions)

        threading.Thread(target=work, daemon=True).start()

    def _captions_segment(self, text: str) -> None:
        self._caption_segment_count = getattr(self, "_caption_segment_count", 0) + 1
        n = self._caption_segment_count
        self.progress_status_var.set(f"Capturing… {n} segments")
        if n <= 15 or n % 30 == 0:
            snippet = text if len(text) <= 120 else text[:117] + "…"
            self._log(f"+ {snippet}")

    def _run_captions_stop(self) -> None:
        if not self._captions_running:
            return
        self._captions_stop.set()
        self._cllog("Stopping…")
        self.captions_stop_btn.configure(state=tk.DISABLED)

    def _finish_captions(self) -> None:
        self._captions_running = False
        self._progress_end()
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
        self._progress_begin(f"Live Whisper ({src_label})…", indeterminate=True)
        self._tlog(f"Live Whisper started ({src_label}) — chunk every {chunk:.0f}s")
        self.status_var.set("Live Whisper listening…")

        def on_text(text: str) -> None:
            self.after(0, lambda t=text: self._tlog(f"» {t}"))

        def on_progress(msg: str) -> None:
            self.after(0, lambda m=msg: self._on_operation_progress(m))

        def work() -> None:
            try:
                self._live_whisper_session.run(
                    stop_event=self._live_whisper_stop,
                    on_text=on_text,
                    on_progress=on_progress,
                )
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
                self.after(0, lambda msg=err: self._tlog(f"Error: {msg}"))
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
        self._progress_end()
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
                    self.after(0, lambda m=msg: self._on_operation_progress(m))

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
                err = f"{type(exc).__name__}: {exc}"
                self.after(0, lambda msg=err: messagebox.showerror("Transcribe failed", msg))
            finally:
                if session:
                    session.stop_auto_capture()
                self.after(0, lambda: self._set_transcribing(False))
                self.after(0, lambda: self._set_busy(False))
                self.after(0, self._progress_end)

        self._set_busy(True)
        self._progress_begin("Transcribing audio…", indeterminate=True)
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

    def _save_cleaned_transcript(self) -> None:
        cleaned = (self._cleaned_text or "").strip()
        if not cleaned:
            messagebox.showwarning("Nothing to save", "Parse & preview first.")
            return
        if not self._source_files:
            messagebox.showwarning("No source", "Add a transcript file first.")
            return
        stem = self._source_files[0].stem
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{stem}_cleaned_{stamp}.txt"
        initial = self.cfg.transcripts_path()
        path = filedialog.asksaveasfilename(
            title="Save cleaned transcript",
            initialdir=str(initial),
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(cleaned, encoding="utf-8")
        self._last_cleaned_path = out
        chars = len(cleaned)
        words = len(cleaned.split())
        self.parse_stats_var.set(f"Saved: {out.name} · {chars:,} chars · {words:,} words")
        self._log(f"Saved cleaned transcript ({chars:,} chars) -> {out}")
        messagebox.showinfo("Saved", f"Cleaned transcript saved:\n{out}\n\n{chars:,} chars · {words:,} words")

    def _run_parse(self) -> None:
        if self._busy:
            return

        def work() -> None:
            try:
                paths = self._resolve_sources()
                transcript_text, _, _, _ = prepare_sources(paths)
                aggressive = self.aggressive_var.get()
                thorough = self.thorough_parse_var.get()
                self.cfg.thorough_parse = thorough
                self.cfg.parse_speed = int(round(self.parse_speed_var.get()))
                save_config(self.cfg)

                def parse_progress(msg: str, frac: float) -> None:
                    self._ui(lambda m=msg, f=frac: self._progress_update(f, m))

                cleaned = parse_transcript(
                    transcript_text,
                    aggressive=aggressive,
                    thorough=thorough,
                    on_progress=parse_progress,
                )
                audit = audit_parse(transcript_text, aggressive=aggressive)
                audit_body = format_audit_report(audit)
                label = paths[0].name if len(paths) == 1 else f"{len(paths)} files combined"
                words = len(cleaned.split())

                def done() -> None:
                    self._cleaned_text = cleaned
                    self._last_cleanup_audit = audit_body
                    chars = len(cleaned)
                    self.parse_stats_var.set(
                        f"Cleaned: {chars:,} chars · {words:,} words · {chars // max(words, 1)} chars/word"
                    )
                    try:
                        self.save_cleaned_btn.configure(state=tk.NORMAL)
                    except tk.TclError:
                        pass
                    self._set_preview_text(self.clean_text, cleaned)
                    self._set_preview_text(self.audit_text, audit_body)
                    self.preview_notebook.select(self.audit_text if audit.review_count else self.clean_text)
                    self._log(f"Parsed {label}: {words:,} words after cleanup")
                    if audit.review_count:
                        self._log(
                            f"Audit: {audit.review_count} item(s) flagged — see Cleanup audit tab"
                        )
                    else:
                        self._log(
                            f"Audit: {audit.word_retention_pct:.0f}% words retained, no obvious loss"
                        )
                    self.status_var.set(
                        f"Cleaned — {words:,} words"
                        + (f" · {audit.review_count} flagged" if audit.review_count else "")
                    )
                    self._progress_end()
                    self._set_busy(False)

                self._ui(done)
            except Exception as exc:
                log_error("Parse failed", exc)
                self._ui(lambda: messagebox.showerror("Parse failed", f"{exc}\n\nDetails: {log_file_path()}"))
                self._ui(self._progress_end)
                self._ui(lambda: self._set_busy(False))

        self._set_busy(True)
        self._progress_begin("Parsing transcript…", indeterminate=True)
        threading.Thread(target=work, daemon=True).start()

    def _summarize_failed(self, message: str) -> None:
        self._log(f"Summarize failed: {message}")
        self._log(f"See log: {log_file_path()}")
        messagebox.showerror("Summarize failed", f"{message}\n\nLog: {log_file_path()}")

    def _run_summarize(self) -> None:
        if self._busy:
            return
        if self._transcribing or self._live_whisper_running:
            messagebox.showwarning(
                "GPU busy",
                "Stop Whisper transcription before summarizing to avoid GPU out-of-memory errors.",
            )
            return
        self._apply_quality_from_preset()
        self._save_settings()
        self._refresh_system_status()
        self._summarize_cancel.clear()

        def work() -> None:
            try:
                if not llm_reachable(options_from_config(self.cfg)):
                    raise RuntimeError(
                        "LLM not reachable. Start LM Studio/Ollama and load your model, then try again."
                    )
                paths = self._resolve_sources()
                title = self.title_var.get().strip() or (
                    paths[0].stem.replace("_", " ") if len(paths) == 1 else "Combined lecture"
                )
                out = Path(self.output_var.get().strip()) if self.output_var.get().strip() else None
                opts = options_from_config(self.cfg)
                context = self._sanitize_context_folder(self.context_var.get().strip() or None)
                if not context and len(paths) > 1:
                    parent = paths[0].parent
                    if self._is_sensible_context_folder(parent):
                        context = str(parent)
                session_dir = None
                if self.cfg.last_session and Path(self.cfg.last_session).is_dir():
                    session_dir = Path(self.cfg.last_session)
                for p in paths:
                    if (p.parent / "snapshots").is_dir():
                        session_dir = p.parent
                        break

                def on_progress(msg: str) -> None:
                    self._ui(lambda m=msg: self._on_operation_progress(m))

                def on_step(current: int, total: int, msg: str) -> None:
                    self._ui(lambda c=current, t=total, m=msg: self._progress_steps(c, t, m))

                pre_cleaned = self._pre_cleaned_for_generate()
                audit_source = pre_cleaned or (self._cleaned_text or "").strip() or None
                note_path, body = generate_notes_from_files(
                    paths,
                    title=title,
                    aggressive=self.aggressive_var.get(),
                    output_dir=out,
                    opts=opts,
                    context_folder=context,
                    fast_mode=self.fast_var.get(),
                    refine_second_pass=self.refine_var.get() and not self.fast_var.get(),
                    enrich_with_references=self.cfg.enrich_with_references and not self.fast_var.get(),
                    use_semantic_grouping=self.semantic_chunk_var.get() and not self.fast_var.get(),
                    use_tag_extraction=self.tags_var.get() and not self.fast_var.get(),
                    inject_wikilinks=self.wikilinks_var.get(),
                    legacy_pipeline=self.legacy_pipeline_var.get(),
                    pre_cleaned=pre_cleaned,
                    max_chunks=self.cfg.max_llm_chunks,
                    session_dir=session_dir,
                    on_progress=on_progress,
                    on_step=on_step,
                    cancel_event=self._summarize_cancel.is_set,
                )

                handoff_summary = ""
                try:
                    from backend.corpus.handoff import ingest_lecture_handoff

                    transcript = next((p for p in paths if p.suffix.lower() == ".txt"), None)
                    if transcript is not None:
                        handoff = ingest_lecture_handoff(
                            transcript_path=transcript,
                            note_path=note_path,
                        )
                        tx_c = handoff.get("transcript_chunks", 0)
                        note_c = handoff.get("note_chunks", 0)
                        handoff_summary = (
                            f"Corpus indexed — transcript {tx_c} chunks, note {note_c} chunks."
                        )
                        self._log(handoff_summary)
                except Exception as exc:
                    handoff_summary = f"Corpus handoff skipped: {exc}"
                    self._log(handoff_summary)

                def done() -> None:
                    self._last_note_path = note_path
                    self._update_done_paths()
                    if audit_source:
                        notes_audit = audit_notes(audit_source, body)
                        notes_audit_body = format_notes_audit_report(notes_audit)
                        self._last_notes_audit = notes_audit_body
                        self._set_preview_text(self.notes_audit_text, notes_audit_body)
                        self._log(
                            f"Notes audit: {notes_audit.word_retention_pct:.1f}% word retention "
                            f"({notes_audit.notes_words:,} / {notes_audit.source_words:,} words)"
                        )
                    else:
                        self._set_preview_text(
                            self.notes_audit_text,
                            "Parse & preview on Tune first to compare cleaned transcript vs generated notes.",
                        )
                    summary = (
                        f"# Saved: {note_path.name}\n\n"
                        f"{len(body):,} characters · see Notes audit tab for retention check.\n\n"
                        f"{body[:2000].strip()}"
                    )
                    if len(body) > 2000:
                        summary += "\n\n… [note preview truncated]"
                    self._set_preview_text(self.clean_text, summary)
                    tab = self.notes_audit_text if audit_source else self.clean_text
                    self.preview_notebook.select(tab)
                    self._show_workflow_step(1)
                    self._log(f"Saved: {note_path}")
                    self.status_var.set(f"Notes saved — {note_path.name}")
                    self._progress_update(1.0, "Complete")
                    audit_hint = (
                        f"\n\nNotes audit: {notes_audit.word_retention_pct:.1f}% retention — see Tune → Notes audit tab."
                        if audit_source
                        else ""
                    )
                    corpus_hint = f"\n\n{handoff_summary}" if handoff_summary else ""
                    messagebox.showinfo("Done", f"Notes saved to:\n{note_path}{audit_hint}{corpus_hint}")
                    self._show_workflow_step(3)

                self._ui(done)
            except Exception as exc:
                log_error("Generate notes failed", exc)
                err = f"{type(exc).__name__}: {exc}"
                self._ui(lambda msg=err: self._summarize_failed(msg))
            finally:
                def reset_ui() -> None:
                    self._set_busy(False)
                    self._progress_end()

                self._ui(reset_ui)

        self._set_busy(True)
        self._progress_begin("Generating notes…")
        self._on_operation_progress("Starting summarization…")
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
    setup_logging()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app = TranscriptStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
