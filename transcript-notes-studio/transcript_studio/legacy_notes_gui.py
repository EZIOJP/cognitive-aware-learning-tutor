"""Classic notes GUI — LM Studio Gemma only, no RAG, no mermaid/code enrich.

Use main Transcript Notes Studio for Capture / Tune when you want manual control.
This window: pick transcripts → classic notes, or Classic Auto (capture → parse → notes → LLM filename).
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from transcript_studio.config import load_config, save_config
from transcript_studio.llm_client import (
    DEFAULT_LMSTUDIO_MODEL,
    LlmOptions,
    llm_reachable,
    lmstudio_loaded_model,
)
from transcript_studio.log_setup import log_error
from transcript_studio.paths import notes_dir, transcripts_dir


class ClassicNotesApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Classic Notes — LM Studio (no RAG / no mermaid)")
        self.geometry("860x720")
        self.cfg = load_config()
        self._busy = False
        self._auto_cancel = threading.Event()
        self._paths: list[Path] = []
        self._build()
        self._refresh_list()

    def _build(self) -> None:
        tip = ttk.Label(
            self,
            text=(
                "Manual: pick a cleaned/raw transcript → LM Studio Gemma notes "
                "(no RAG, no diagrams). Auto: Live Captions → parse → classic notes → "
                "LLM names the .md file."
            ),
            wraplength=820,
        )
        tip.pack(fill=tk.X, padx=12, pady=(12, 6))

        row = ttk.Frame(self)
        row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(row, text="LM Studio URL").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value=self.cfg.llm_base_url or "http://127.0.0.1:1234")
        ttk.Entry(row, textvariable=self.url_var, width=36).pack(side=tk.LEFT, padx=6)
        ttk.Label(row, text="Model").pack(side=tk.LEFT)
        configured = (self.cfg.llm_model or "").strip()
        if not configured or any(
            x in configured.lower() for x in ("gemini", "gpt", "claude", "openrouter")
        ):
            configured = DEFAULT_LMSTUDIO_MODEL
        self.model_var = tk.StringVar(value=configured)
        ttk.Entry(row, textvariable=self.model_var, width=28).pack(side=tk.LEFT, padx=6)

        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, padx=12, pady=4)
        self.status_var = tk.StringVar(value="Checking LM Studio…")
        ttk.Label(row2, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Button(row2, text="Ping LM Studio", command=self._ping).pack(side=tk.RIGHT)

        auto = ttk.LabelFrame(self, text="Classic Auto (capture → parse → notes → LLM filename)", padding=8)
        auto.pack(fill=tk.X, padx=12, pady=6)
        ttk.Label(
            auto,
            text="Enable Live Captions (Win+Ctrl+L) before Start. Stops on silence or max duration.",
            wraplength=800,
        ).pack(anchor=tk.W)
        opts = ttk.Frame(auto)
        opts.pack(fill=tk.X, pady=(6, 4))
        ttk.Label(opts, text="Idle stop (sec)").pack(side=tk.LEFT)
        self.idle_var = tk.StringVar(value=str(int(self.cfg.lecture_auto_idle_sec or 600)))
        ttk.Entry(opts, textvariable=self.idle_var, width=8).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(opts, text="Max duration (sec, 0=off)").pack(side=tk.LEFT)
        self.max_var = tk.StringVar(value=str(int(self.cfg.lecture_auto_max_sec or 7500)))
        ttk.Entry(opts, textvariable=self.max_var, width=8).pack(side=tk.LEFT, padx=(6, 0))
        btns = ttk.Frame(auto)
        btns.pack(fill=tk.X, pady=(4, 0))
        self.auto_btn = ttk.Button(btns, text="Start Classic Auto", command=self._run_auto)
        self.auto_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(
            btns, text="Cancel", command=self._cancel_auto, state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.auto_status_var = tk.StringVar(value="")
        ttk.Label(auto, textvariable=self.auto_status_var, wraplength=800).pack(
            anchor=tk.W, pady=(6, 0)
        )

        mid = ttk.LabelFrame(self, text="Transcripts (manual generate)", padding=8)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        list_btns = ttk.Frame(mid)
        list_btns.pack(fill=tk.X)
        ttk.Button(list_btns, text="Refresh", command=self._refresh_list).pack(side=tk.LEFT)
        ttk.Button(list_btns, text="Open transcripts folder", command=self._open_tx).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(list_btns, text="Open notes folder", command=self._open_notes).pack(side=tk.LEFT)

        self.listbox = tk.Listbox(mid, height=10, selectmode=tk.EXTENDED)
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, padx=12, pady=6)
        self.gen_btn = ttk.Button(
            actions,
            text="Generate classic notes (LM Studio · no RAG · no mermaid)",
            command=self._run_generate,
        )
        self.gen_btn.pack(side=tk.LEFT)
        ttk.Button(actions, text="Save LM settings", command=self._save_settings).pack(
            side=tk.LEFT, padx=8
        )

        self.log = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=False, padx=12, pady=(0, 12))
        self.after(200, self._ping)

    def _opts(self) -> LlmOptions:
        return LlmOptions(
            provider="lmstudio",
            base_url=self.url_var.get().strip().rstrip("/") or "http://127.0.0.1:1234",
            model=self.model_var.get().strip() or DEFAULT_LMSTUDIO_MODEL,
            max_tokens=int(getattr(self.cfg, "llm_max_tokens", 8192) or 8192),
            temperature=float(getattr(self.cfg, "llm_temperature", 0.3) or 0.3),
            api_key=self.cfg.llm_api_key or "lm-studio",
        )

    def _apply_lm_to_cfg(self) -> LlmOptions:
        opts = self._opts()
        # Prefer whatever LLM is currently loaded in LM Studio.
        loaded = lmstudio_loaded_model(opts.base_url, api_key=opts.api_key)
        if loaded and loaded != opts.model:
            self.model_var.set(loaded)
            opts = self._opts()
        self.cfg.llm_provider = "lmstudio"
        self.cfg.llm_base_url = opts.base_url
        self.cfg.llm_model = opts.model
        self.cfg.llm_use_gateway = False
        self.cfg.legacy_notes_pipeline = True
        self.cfg.enrich_visuals = False
        return opts

    def _ping(self) -> None:
        opts = self._apply_lm_to_cfg()
        ok = llm_reachable(opts)
        self.status_var.set(
            f"LM Studio {'reachable' if ok else 'OFFLINE'} · {opts.base_url} · {opts.model}"
        )

    def _save_settings(self) -> None:
        self._apply_lm_to_cfg()
        try:
            self.cfg.lecture_auto_idle_sec = max(60.0, float(self.idle_var.get().strip() or "600"))
        except ValueError:
            self.cfg.lecture_auto_idle_sec = 600.0
        try:
            self.cfg.lecture_auto_max_sec = max(0.0, float(self.max_var.get().strip() or "7500"))
        except ValueError:
            self.cfg.lecture_auto_max_sec = 7500.0
        save_config(self.cfg)
        self._append("Settings saved (lmstudio, gateway off, legacy on, enrich off).")
        self._ping()

    def _refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        folder = transcripts_dir()
        paths = sorted(folder.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        self._paths = paths
        for p in paths:
            self.listbox.insert(tk.END, p.name)

    def _selected(self) -> list[Path]:
        idxs = self.listbox.curselection()
        return [self._paths[i] for i in idxs if 0 <= i < len(self._paths)]

    def _open_tx(self) -> None:
        import os

        os.startfile(str(transcripts_dir()))  # noqa: S606 — Windows explorer

    def _open_notes(self) -> None:
        import os

        os.startfile(str(notes_dir()))  # noqa: S606

    def _append(self, msg: str) -> None:
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def _ensure_lm(self) -> LlmOptions | None:
        opts = self._apply_lm_to_cfg()
        if not llm_reachable(opts):
            messagebox.showerror(
                "LM Studio offline",
                f"Start LM Studio local server and load {opts.model}.\n{opts.base_url}",
            )
            return None
        return opts

    def _run_auto(self) -> None:
        if self._busy:
            return
        opts = self._ensure_lm()
        if opts is None:
            return
        try:
            idle = max(60.0, float(self.idle_var.get().strip() or "600"))
        except ValueError:
            idle = 600.0
        try:
            max_sec = max(0.0, float(self.max_var.get().strip() or "7500"))
        except ValueError:
            max_sec = 7500.0
        self.cfg.lecture_auto_idle_sec = idle
        self.cfg.lecture_auto_max_sec = max_sec
        save_config(self.cfg)

        if not messagebox.askyesno(
            "Classic Auto",
            "Start Classic Auto?\n\n"
            "1. Capture Live Captions (enable Win+Ctrl+L)\n"
            f"2. Stop after {int(idle)}s silence"
            + (f" or {int(max_sec)}s max" if max_sec > 0 else "")
            + "\n"
            "3. Parse + LM Studio classic notes (no RAG / no mermaid)\n"
            "4. LLM names the output .md file\n\nContinue?",
        ):
            return

        self._auto_cancel.clear()
        self._set_busy(True, auto=True)
        self.auto_status_var.set("starting…")
        self._append("Classic Auto started — enable Live Captions (Win+Ctrl+L)")

        def on_phase(phase: str, message: str) -> None:
            def update(p: str = phase, m: str = message) -> None:
                self.auto_status_var.set(f"{p}: {m}")
                self._append(f"[{p}] {m}")

            self.after(0, update)

        def on_progress(msg: str) -> None:
            self.after(0, lambda m=msg: self._append(m))

        def work() -> None:
            from transcript_studio.classic_auto import run_classic_auto

            try:
                result = run_classic_auto(
                    self.cfg,
                    opts=opts,
                    on_phase=on_phase,
                    on_progress=on_progress,
                    cancel_event=self._auto_cancel,
                    idle_sec=idle,
                    max_sec=max_sec if max_sec > 0 else None,
                )

                def done() -> None:
                    self._finish_auto(result)

                self.after(0, done)
            except Exception as exc:
                log_error("Classic Auto failed", exc)

                def fail() -> None:
                    messagebox.showerror("Classic Auto failed", str(exc))
                    self._set_busy(False)

                self.after(0, fail)

        threading.Thread(target=work, daemon=True).start()

    def _cancel_auto(self) -> None:
        self._auto_cancel.set()
        self.auto_status_var.set("cancelling…")
        self._append("Cancel requested…")

    def _finish_auto(self, result: object) -> None:
        self._set_busy(False)
        self._refresh_list()
        success = bool(getattr(result, "success", False))
        note_path = getattr(result, "note_path", None)
        title = getattr(result, "title", "") or ""
        err = getattr(result, "error", "") or ""
        log_path = getattr(result, "log_path", "") or ""
        if success and note_path is not None:
            self.auto_status_var.set(f"done: {Path(note_path).name}")
            self._append(f"Classic Auto complete — {title} → {note_path}")
            if log_path:
                self._append(f"Log: {log_path}")
            messagebox.showinfo(
                "Classic Auto done",
                f"Title: {title}\n\nSaved:\n{note_path}",
            )
        else:
            self.auto_status_var.set(f"failed: {err}" if err else "failed")
            self._append(f"Classic Auto failed: {err}")
            if log_path:
                self._append(f"Log: {log_path}")
            messagebox.showerror("Classic Auto failed", err or "Unknown error")

    def _run_generate(self) -> None:
        if self._busy:
            return
        paths = self._selected()
        if not paths:
            messagebox.showwarning("Select transcript", "Select one or more .txt files.")
            return
        opts = self._ensure_lm()
        if opts is None:
            return

        def work() -> None:
            try:
                from transcript_studio.notes_generator import generate_notes_from_file

                for i, path in enumerate(paths, 1):
                    self.after(
                        0,
                        lambda m=f"[{i}/{len(paths)}] Classic notes: {path.name}": self._append(m),
                    )

                    def on_progress(msg: str) -> None:
                        self.after(0, lambda m=msg: self._append(m))

                    note_path, _body, mode = generate_notes_from_file(
                        path,
                        title=path.stem.replace("_", " "),
                        aggressive=True,
                        opts=opts,
                        legacy_pipeline=True,
                        assemble_mode=False,
                        enrich_visuals=False,
                        fast_mode=True,
                        refine_second_pass=False,
                        use_semantic_grouping=False,
                        use_tag_extraction=False,
                        inject_wikilinks=False,
                        classic_lmstudio=True,
                        on_progress=on_progress,
                    )
                    self.after(
                        0,
                        lambda p=note_path, m=mode: self._append(f"Saved ({m}): {p.name}"),
                    )
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Done",
                        f"Generated {len(paths)} classic note(s) in:\n{notes_dir()}",
                    ),
                )
            except Exception as exc:
                log_error("Classic notes failed", exc)
                self.after(0, lambda: messagebox.showerror("Classic notes failed", str(exc)))
            finally:
                self.after(0, lambda: self._set_busy(False))

        self._set_busy(True)
        self._append("Starting classic LM Studio generation…")
        threading.Thread(target=work, daemon=True).start()

    def _set_busy(self, busy: bool, *, auto: bool = False) -> None:
        self._busy = busy
        self.gen_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.auto_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        if auto and busy:
            self.cancel_btn.configure(state=tk.NORMAL)
        else:
            self.cancel_btn.configure(state=tk.DISABLED)


def main() -> None:
    app = ClassicNotesApp()
    app.mainloop()


if __name__ == "__main__":
    main()
