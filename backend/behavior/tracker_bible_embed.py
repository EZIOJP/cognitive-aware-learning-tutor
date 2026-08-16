"""Embedded Good News Bible reader for the hard-block popup (PyMuPDF → Tk)."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("desktop_tracker")

_embedded_reading = False
_embedded_lock = threading.Lock()
_credit_user_id: int | None = None


def is_embedded_bible_reading() -> bool:
    with _embedded_lock:
        return _embedded_reading


def set_credit_user_id(user_id: int | None) -> None:
    global _credit_user_id
    _credit_user_id = int(user_id) if user_id else None


def _set_embedded_reading(active: bool) -> None:
    global _embedded_reading
    with _embedded_lock:
        _embedded_reading = bool(active)


def _credit_tick(seconds: float = 2.0) -> None:
    uid = _credit_user_id
    if not uid or not is_embedded_bible_reading():
        return
    try:
        from backend.bible import store as bible_store

        bible_store.credit_reading_seconds(uid, seconds)
    except Exception as exc:  # noqa: BLE001
        log.debug("embedded bible credit failed: %s", exc)


class EmbeddedBiblePane:
    """Scrollable page viewer with visual chapter checkpoints (no bank reward)."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_status: Callable[[str], None] | None = None,
        on_page: Callable[[int], None] | None = None,
    ) -> None:
        self.parent = parent
        self.on_status = on_status or (lambda _s: None)
        self.on_page = on_page or (lambda _p: None)
        self.doc: Any = None
        self.page_index = 0
        self._photo: Any = None
        self._credit_after: str | None = None
        self._chapters: list[dict[str, Any]] = []
        self._completed: set[str] = set()
        self._manual: set[str] = set()
        self._bookmarked_pages: set[int] = set()
        self._long_press_ms = 550
        self._press_job: str | None = None
        self._press_fired = False

        self.frame = tk.Frame(parent, bg="#0f172a")

        chapter_row = tk.Frame(self.frame, bg="#0f172a")
        chapter_row.pack(fill=tk.X, pady=(0, 4))

        self.chapter_var = tk.StringVar(value="Chapters: scanning…")
        self.chapter_bar = tk.Label(
            chapter_row,
            textvariable=self.chapter_var,
            bg="#0f172a",
            fg="#94a3b8",
            font=("Segoe UI", 9),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=720,
        )
        self.chapter_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.tick_btn = tk.Button(
            chapter_row,
            text="☑ Tick chapter",
            command=self.toggle_current_chapter,
            bg="#ca8a04",
            fg="#0f172a",
            activebackground="#eab308",
            activeforeground="#0f172a",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.tick_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.chip_row = tk.Frame(self.frame, bg="#0f172a")
        self.chip_row.pack(fill=tk.X, pady=(0, 4))

        toolbar = tk.Frame(self.frame, bg="#0f172a")
        toolbar.pack(fill=tk.X, pady=(0, 6))

        self.prev_btn = tk.Button(
            toolbar,
            text="◀ Prev",
            command=self.prev_page,
            bg="#334155",
            fg="#e2e8f0",
            activebackground="#475569",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        self.prev_btn.pack(side=tk.LEFT)

        self.page_label = tk.Label(
            toolbar,
            text="—",
            bg="#0f172a",
            fg="#f8fafc",
            font=("Segoe UI", 10, "bold"),
        )
        self.page_label.pack(side=tk.LEFT, padx=12)

        self.next_btn = tk.Button(
            toolbar,
            text="Next ▶",
            command=self.next_page,
            bg="#334155",
            fg="#e2e8f0",
            activebackground="#475569",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        self.next_btn.pack(side=tk.LEFT)

        tk.Label(
            toolbar,
            text="Reading here counts toward Bible time",
            bg="#0f172a",
            fg="#94a3b8",
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT)

        canvas_wrap = tk.Frame(self.frame, bg="#1e293b")
        canvas_wrap.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_wrap, bg="#1e293b", highlightthickness=0)
        vsb = tk.Scrollbar(canvas_wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.img_id: int | None = None
        self._render_job: str | None = None
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    def pack(self, **kwargs: Any) -> None:
        self.frame.pack(**kwargs)

    def destroy(self) -> None:
        self._persist_page()
        self.stop_credit_loop()
        _set_embedded_reading(False)
        try:
            if self.doc is not None:
                self.doc.close()
        except Exception:  # noqa: BLE001
            pass
        self.doc = None

    def _on_configure(self, _event: tk.Event) -> None:
        if self._render_job is not None:
            try:
                self.frame.after_cancel(self._render_job)
            except tk.TclError:
                pass
        try:
            self._render_job = self.frame.after(120, lambda: self._render_current(fit_width=True))
        except tk.TclError:
            self._render_job = None

    def open_pdf(self, path: Path) -> bool:
        try:
            import fitz
        except ImportError:
            self.on_status("PyMuPDF missing — cannot embed PDF")
            return False
        try:
            if self.doc is not None:
                self.doc.close()
            self.doc = fitz.open(str(path))
            start = 0
            uid = _credit_user_id
            if uid:
                try:
                    from backend.bible import store as bible_store

                    start = max(0, bible_store.get_last_page(uid) - 1)
                    self._completed = set(bible_store.get_completed_chapters(uid))
                    self._manual = set(bible_store.get_manual_chapters(uid))
                    self._bookmarked_pages = {
                        int(b["page"]) for b in bible_store.list_bookmarks(uid)
                    }
                except Exception as exc:  # noqa: BLE001
                    log.debug("load reader state failed: %s", exc)
            n = len(self.doc)
            if n > 0:
                start = min(start, n - 1)
            self.page_index = start
            self._jumped_today = False
            _set_embedded_reading(True)
            self._render_current(fit_width=True)
            self.start_credit_loop()
            self.on_status(f"Opened {path.name} · page {self.page_index + 1}")
            self.on_page(self.page_index + 1)
            # Build chapter index off the UI thread-ish via after
            self.frame.after(200, self._load_chapters)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("embed bible failed: %s", exc)
            self.on_status(f"Could not open PDF: {exc}")
            return False

    def _load_chapters(self) -> None:
        try:
            from backend.bible.chapters import load_or_build_chapters

            self._chapters = load_or_build_chapters()
            self._refresh_chapter_bar()
            self._sync_chapter_completion()
        except Exception as exc:  # noqa: BLE001
            log.warning("chapter index failed: %s", exc)
            self.chapter_var.set("Chapters: (index unavailable)")

    def _sync_chapter_completion(self) -> None:
        """Refresh tick UI from store — never auto-complete from PDF page position."""
        uid = _credit_user_id
        if uid:
            try:
                from backend.bible import store as bible_store

                self._completed = set(bible_store.get_completed_chapters(uid))
                self._manual = set(bible_store.get_manual_chapters(uid))
            except Exception as exc:  # noqa: BLE001
                log.debug("load chapter ticks failed: %s", exc)
        self._refresh_chapter_bar()

    def _current_chapter_key(self) -> str | None:
        from backend.bible.chapters import chapter_at_page

        cur = chapter_at_page(self._chapters, self.page_index + 1) if self._chapters else None
        if not cur:
            return None
        return f"{cur['book']}|{cur['chapter']}"

    def toggle_current_chapter(self) -> None:
        uid = _credit_user_id
        if uid:
            try:
                from backend.bible import store as bible_store

                today = bible_store.resolve_today_chapter(uid)
                self._toggle_chapter_key(str(today["key"]))
                return
            except Exception as exc:  # noqa: BLE001
                log.debug("today tick fallback: %s", exc)
        key = self._current_chapter_key()
        if not key:
            self.on_status("No chapter detected on this page")
            return
        self._toggle_chapter_key(key)

    def _toggle_chapter_key(self, key: str) -> None:
        uid = _credit_user_id
        if not uid:
            # Local-only toggle when no user
            if key in self._completed:
                self._completed.discard(key)
                self._manual.discard(key)
                marked = False
            else:
                self._completed.add(key)
                self._manual.add(key)
                marked = True
        else:
            try:
                from backend.bible import store as bible_store

                result = bible_store.toggle_chapter_manual(uid, key)
                marked = bool(result.get("completed"))
                self._completed = set(bible_store.get_completed_chapters(uid))
                self._manual = set(bible_store.get_manual_chapters(uid))
            except Exception as exc:  # noqa: BLE001
                log.warning("toggle chapter failed: %s", exc)
                return
        book, _, chap = key.partition("|")
        self.on_status(
            f"{'Ticked' if marked else 'Cleared'} {book} ch.{chap} (manual)"
        )
        self._refresh_chapter_bar()

    def _bookmark_chapter(self, chapter: dict[str, Any]) -> None:
        page = int(chapter["start_page"])
        label = f"{chapter['book']} {chapter['chapter']}"
        uid = _credit_user_id
        if not uid:
            self._bookmarked_pages.add(page)
            self.on_status(f"Bookmarked {label} (local)")
            self._refresh_chapter_bar()
            return
        try:
            from backend.bible import store as bible_store

            # Avoid duplicate bookmark for same page
            existing = bible_store.list_bookmarks(uid)
            if any(int(b["page"]) == page for b in existing):
                self.on_status(f"Already bookmarked: {label}")
                return
            bible_store.add_bookmark(uid, page, label)
            self._bookmarked_pages = {int(b["page"]) for b in bible_store.list_bookmarks(uid)}
            self.on_status(f"Bookmarked {label} · p.{page}")
            self._refresh_chapter_bar()
        except Exception as exc:  # noqa: BLE001
            log.warning("bookmark chapter failed: %s", exc)
            self.on_status("Bookmark failed")

    def _bind_chip(
        self,
        btn: tk.Button,
        *,
        key: str,
        chapter: dict[str, Any],
    ) -> None:
        """Click = check/uncheck. Long-press = bookmark chapter start."""
        state: dict[str, Any] = {"job": None, "long": False}

        def on_press(_event: tk.Event | None = None) -> None:
            state["long"] = False
            if state["job"] is not None:
                try:
                    self.frame.after_cancel(state["job"])
                except tk.TclError:
                    pass

            def fire_long() -> None:
                state["long"] = True
                state["job"] = None
                self._bookmark_chapter(chapter)

            try:
                state["job"] = self.frame.after(self._long_press_ms, fire_long)
            except tk.TclError:
                state["job"] = None

        def on_release(_event: tk.Event | None = None) -> None:
            if state["job"] is not None:
                try:
                    self.frame.after_cancel(state["job"])
                except tk.TclError:
                    pass
                state["job"] = None
            if state["long"]:
                return
            self._toggle_chapter_key(key)

        def on_leave(_event: tk.Event | None = None) -> None:
            if state["job"] is not None:
                try:
                    self.frame.after_cancel(state["job"])
                except tk.TclError:
                    pass
                state["job"] = None

        btn.bind("<ButtonPress-1>", on_press)
        btn.bind("<ButtonRelease-1>", on_release)
        btn.bind("<Leave>", on_leave)

    def _refresh_chapter_bar(self) -> None:
        from backend.bible.chapters import chapter_at_page

        page = self.page_index + 1
        for child in self.chip_row.winfo_children():
            child.destroy()

        uid = _credit_user_id
        today = None
        if uid:
            try:
                from backend.bible import store as bible_store

                today = bible_store.resolve_today_chapter(uid)
            except Exception as exc:  # noqa: BLE001
                log.debug("today chapter resolve failed: %s", exc)

        cur = chapter_at_page(self._chapters, page) if self._chapters else None

        # Today-only: hide book/chapter browser; show assigned chapter + tick
        if today:
            key = str(today["key"])
            label = str(today["label"])
            done = bool(today.get("done")) or key in self._completed
            if done:
                self.tick_btn.configure(text="☐ Clear tick", state=tk.NORMAL)
            else:
                self.tick_btn.configure(text="☑ Mark done", state=tk.NORMAL)
            self.chapter_var.set(
                f"Today: {label}"
                + ("  ·  Done for today" if done else "  ·  Read & tick this chapter only")
            )
            # Jump PDF to today's chapter if index knows it
            if self._chapters and not done:
                match = next(
                    (
                        c
                        for c in self._chapters
                        if c["book"] == today["book"] and int(c["chapter"]) == int(today["chapter"])
                    ),
                    None,
                )
                if match and cur and (
                    cur["book"] != today["book"] or int(cur["chapter"]) != int(today["chapter"])
                ):
                    # Only auto-jump once per open — avoid fighting user page turns within chapter
                    if not getattr(self, "_jumped_today", False):
                        self._jumped_today = True
                        target = max(0, int(match["start_page"]) - 1)
                        if self.doc is not None and target != self.page_index:
                            self.page_index = min(target, len(self.doc) - 1)
                            self._render_current(fit_width=True)
                            self.on_page(self.page_index + 1)
            return

        if not cur:
            self.chapter_var.set(f"Page {page} · chapter unknown")
            self.tick_btn.configure(text="☑ Tick chapter", state=tk.DISABLED)
            return

        book = str(cur["book"])
        cur_key = f"{book}|{cur['chapter']}"
        if cur_key in self._completed:
            self.tick_btn.configure(text="☐ Clear tick", state=tk.NORMAL)
        else:
            self.tick_btn.configure(text="☑ Tick chapter", state=tk.NORMAL)

        # No chapter chip strip — today-only mode hides other books/chapters
        self.chapter_var.set(
            f"{book} ch.{cur['chapter']} (pp.{cur['start_page']}–{cur['end_page']})"
        )

    def start_credit_loop(self) -> None:
        self.stop_credit_loop()

        def tick() -> None:
            if not is_embedded_bible_reading():
                return
            _credit_tick(2.0)
            try:
                self._credit_after = self.frame.after(2000, tick)
            except tk.TclError:
                self._credit_after = None

        try:
            self._credit_after = self.frame.after(2000, tick)
        except tk.TclError:
            self._credit_after = None

    def stop_credit_loop(self) -> None:
        if self._credit_after is not None:
            try:
                self.frame.after_cancel(self._credit_after)
            except tk.TclError:
                pass
            self._credit_after = None

    def _persist_page(self) -> None:
        uid = _credit_user_id
        if not uid:
            return
        try:
            from backend.bible import store as bible_store

            bible_store.save_last_page(uid, self.page_index + 1)
        except Exception as exc:  # noqa: BLE001
            log.debug("save last_page failed: %s", exc)

    def prev_page(self) -> None:
        if self.doc is None:
            return
        self.page_index = max(0, self.page_index - 1)
        self._after_page_change()

    def next_page(self) -> None:
        if self.doc is None:
            return
        self.page_index = min(len(self.doc) - 1, self.page_index + 1)
        self._after_page_change()

    def _after_page_change(self) -> None:
        self._render_current(fit_width=True)
        self._persist_page()
        self._sync_chapter_completion()
        self.on_page(self.page_index + 1)

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _render_current(self, *, fit_width: bool = True) -> None:
        if self.doc is None:
            return
        try:
            import fitz
        except ImportError:
            return
        n = len(self.doc)
        if n <= 0:
            return
        self.page_index = max(0, min(self.page_index, n - 1))
        self.page_label.configure(text=f"Page {self.page_index + 1} / {n}")
        page = self.doc.load_page(self.page_index)
        target_w = max(320, int(self.canvas.winfo_width()) - 16)
        if target_w < 100:
            target_w = 720
        zoom = target_w / max(1.0, float(page.rect.width)) if fit_width else 1.2
        zoom = max(0.6, min(zoom, 2.5))
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.on_status("Pillow missing — cannot show PDF pages")
            return
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        photo = ImageTk.PhotoImage(img)
        self._photo = photo
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(8, 8, anchor=tk.NW, image=photo)
        self.canvas.configure(scrollregion=(0, 0, pix.width + 16, pix.height + 16))
