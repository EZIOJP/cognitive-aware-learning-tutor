"""Capture Windows Live Captions text via UI Automation (pywinauto).

Recording quality borrows SaveLiveCaptions ideas (stable sentence gate,
better-version replace, optional timestamps) while keeping CALT attach,
seed-baseline, idle stop, OCR fallback, and Studio wiring.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from backend.paths import TRANSCRIPTS_DIR
from backend.transcripts.caption_stabilize import (
    CaptionStabilizer,
    similarity_ratio,
    strip_caption_timestamp,
)
from backend.transcripts.cleanup import normalize_segment

CAPTIONS_EXE = "LiveCaptions.exe"
CAPTIONS_AUTO_ID = "CaptionsTextBlock"
_LC_TITLES = ("Live Captions", "Live captions")
_ATTACH_HINT = (
    "Start Windows Live Captions with Win+Ctrl+L (black caption bar). "
    "Studio does not read DeLive, YouTube, or browser captions."
)
_SESSION_BREAK = "--- session break ---"
_DOUBT_BREAK_RE = re.compile(
    r"\b(?:any questions?|doubts?|thumbs up|clear with this slide)\b",
    re.IGNORECASE,
)
_HEARTBEAT_SEC = 30.0


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _longest_line_overlap(prev_lines: list[str], curr_lines: list[str]) -> int:
    best = 0
    for i in range(1, min(len(prev_lines), len(curr_lines)) + 1):
        if prev_lines[-i:] == curr_lines[:i]:
            best = i
    return best


def extract_caption_delta(previous: str, current: str) -> str | None:
    """Return newly spoken text when Live Captions updates its text block."""
    previous = previous.strip()
    current = current.strip()
    if not current:
        return None
    if current == previous:
        return None
    if previous and current.startswith(previous):
        delta = current[len(previous) :].strip()
        return delta or None

    prev_lines = _split_lines(previous)
    curr_lines = _split_lines(current)
    if not prev_lines:
        return current
    if not curr_lines:
        return None

    overlap = _longest_line_overlap(prev_lines, curr_lines)
    if overlap > 0:
        new_lines = curr_lines[overlap:]
        return "\n".join(new_lines) if new_lines else None

    last_prev, first_curr = prev_lines[-1], curr_lines[0]
    if first_curr.startswith(last_prev) and len(first_curr) > len(last_prev):
        remainder = first_curr[len(last_prev) :].strip()
        parts = ([remainder] if remainder else []) + curr_lines[1:]
        return "\n".join(parts) if parts else None

    prev_set = set(prev_lines)
    new_only = [ln for ln in curr_lines if ln not in prev_set]
    return "\n".join(new_only) if new_only else None


def find_live_captions_pid() -> int | None:
    """Return LiveCaptions.exe PID on Windows, or None if not running."""
    if platform.system() != "Windows":
        return None
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {CAPTIONS_EXE}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        line = line.strip().strip('"')
        if not line or CAPTIONS_EXE.lower() not in line.lower():
            continue
        # CSV: "LiveCaptions.exe","32828","Console","1","12,345 K"
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    return None


def find_live_captions_hwnd() -> int | None:
    """Fast Win32 FindWindow for the Live Captions top-level window."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = int(user32.FindWindowW("LiveCaptionsDesktopWindow", None) or 0)
        if hwnd:
            return hwnd
        for title in _LC_TITLES:
            hwnd = int(user32.FindWindowW(None, title) or 0)
            if hwnd:
                return hwnd
        return None
    except Exception:
        return None


def live_captions_exe_path() -> Path | None:
    if platform.system() != "Windows":
        return None
    roots = [
        os.environ.get("SystemRoot", r"C:\Windows"),
        r"C:\Windows",
    ]
    seen: set[str] = set()
    for root in roots:
        path = Path(root) / "System32" / CAPTIONS_EXE
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return path
    return None


def launch_live_captions() -> bool:
    """Start LiveCaptions.exe if it is not already running."""
    if platform.system() != "Windows":
        return False
    if find_live_captions_pid() is not None:
        return True
    exe = live_captions_exe_path()
    if exe is None:
        return False
    try:
        subprocess.Popen(
            [str(exe)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def wait_for_live_captions(*, timeout: float = 8.0) -> tuple[int | None, int | None]:
    """Poll until the Live Captions window exists (PID alone is not enough)."""
    deadline = time.monotonic() + max(0.0, timeout)
    hwnd = find_live_captions_hwnd()
    pid = find_live_captions_pid()
    while time.monotonic() < deadline:
        if pid and not hwnd:
            hwnd = find_hwnd_for_pid(pid) or find_live_captions_hwnd()
        if hwnd:
            return hwnd, pid or find_live_captions_pid()
        time.sleep(0.25)
        hwnd = find_live_captions_hwnd()
        pid = find_live_captions_pid()
    if pid and not hwnd:
        hwnd = find_hwnd_for_pid(pid)
    return hwnd, pid


def find_hwnd_for_pid(pid: int) -> int | None:
    """Win32 enum (not UIA) — visible window belonging to LiveCaptions.exe."""
    if platform.system() != "Windows" or not pid:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found: list[int] = []
        captionish: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            proc = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
            if int(proc.value) != int(pid):
                return True
            length = int(user32.GetWindowTextLengthW(hwnd) or 0)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = (buf.value or "").strip()
            hwnd_i = int(hwnd)
            if "caption" in title.lower():
                captionish.append(hwnd_i)
                return False
            found.append(hwnd_i)
            return True

        user32.EnumWindows(callback, 0)
        return (captionish or found or [None])[0]
    except Exception:
        return None


@dataclass
class _UiaRect:
    left: int
    top: int
    right: int
    bottom: int


class _UiaCaptionBlock:
    """CaptionsTextBlock via ElementFromHandle — never walks the whole desktop."""

    def __init__(self, hwnd: int, uia, text_element) -> None:
        self._hwnd = int(hwnd)
        self._uia = uia
        self._text = text_element

    def window_text(self) -> str:
        try:
            return (self._text.CurrentName or "").strip()
        except Exception:
            refreshed = _resolve_captions_text_element(self._uia, self._hwnd)
            if refreshed is None:
                return ""
            self._text = refreshed
            try:
                return (self._text.CurrentName or "").strip()
            except Exception:
                return ""

    def rectangle(self) -> _UiaRect:
        rect = self._text.CurrentBoundingRectangle
        left = int(getattr(rect, "left", 0) or 0)
        top = int(getattr(rect, "top", 0) or 0)
        right = int(getattr(rect, "right", left) or left)
        bottom = int(getattr(rect, "bottom", top) or top)
        return _UiaRect(left=left, top=top, right=right, bottom=bottom)


def _resolve_captions_text_element(uia, hwnd: int):
    root = uia.ElementFromHandle(int(hwnd))
    if root is None:
        return None
    # UIA_AutomationIdPropertyId = 30011, TreeScope_Descendants = 4
    cond = uia.CreatePropertyCondition(30011, CAPTIONS_AUTO_ID)
    found = root.FindFirst(4, cond)
    if found is not None:
        return found
    # UIA_ControlTypePropertyId = 30003, UIA_TextControlTypeId = 50020
    text_cond = uia.CreatePropertyCondition(30003, 50020)
    return root.FindFirst(4, text_cond)


def _open_uia_caption_block(hwnd: int) -> _UiaCaptionBlock:
    """Attach to CaptionsTextBlock using handle-scoped UI Automation (not pywinauto)."""
    try:
        import comtypes.client
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
    except ImportError:
        import comtypes.client

        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation

    uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
    text_el = _resolve_captions_text_element(uia, hwnd)
    if text_el is None:
        raise RuntimeError(
            "Could not find CaptionsTextBlock in the Live Captions window. "
            f"{_ATTACH_HINT}"
        )
    return _UiaCaptionBlock(hwnd, uia, text_el)


@dataclass
class LiveCaptionsScraper:
    """Poll Windows Live Captions and accumulate transcript lines."""

    poll_interval: float = 0.35
    method: Literal["uia", "ocr"] = "uia"
    # SaveLiveCaptions-inspired quality knobs (safe defaults).
    stable_threshold: int = 3
    min_commit_chars: int = 10
    similarity: float = 0.85
    timestamps: bool = True
    on_segment: Callable[[str], None] | None = None
    on_heartbeat: Callable[[int, float], None] | None = None
    on_ready: Callable[[int], None] | None = None  # seeded baseline char count
    segments: list[str] = field(default_factory=list)
    _segment_times: list[float] = field(default_factory=list)
    _last_block: str = ""
    _seeded: bool = False
    _stabilizer: CaptionStabilizer | None = None

    def __post_init__(self) -> None:
        self._stabilizer = CaptionStabilizer(
            stable_threshold=max(1, int(self.stable_threshold)),
            min_length=max(1, int(self.min_commit_chars)),
            similarity=float(self.similarity),
        )
        if self.method == "ocr":
            try:
                import pytesseract  # noqa: F401
                from PIL import ImageGrab  # noqa: F401
            except ImportError:
                print(
                    "OCR method selected but pytesseract/Pillow missing — using UIA instead.",
                    file=sys.stderr,
                    flush=True,
                )
                self.method = "uia"

    def _connect_uia(self):
        if platform.system() != "Windows":
            raise OSError("Live Captions scraping requires Windows.")

        try:
            import comtypes.client  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "comtypes is required. Install with: pip install -r backend/requirements-captions.txt"
            ) from exc

        # HWND / PID only — never pywinauto connect(title=…). UIA title search
        # walks every top-level window and hangs on Chrome/Electron (e.g. DeLive).
        hwnd = find_live_captions_hwnd()
        pid = find_live_captions_pid()
        if not hwnd and not pid:
            if launch_live_captions():
                hwnd, pid = wait_for_live_captions(timeout=8.0)
        if not hwnd and pid:
            hwnd = find_hwnd_for_pid(pid)

        if not hwnd:
            raise RuntimeError(
                "Could not attach to Windows Live Captions. "
                f"{_ATTACH_HINT} (window not ready; LiveCaptions.exe pid={pid or 'none'})"
            )

        try:
            return _open_uia_caption_block(int(hwnd))
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Could not attach to Windows Live Captions. {_ATTACH_HINT} ({exc})"
            ) from exc

    def _read_uia(self, text_block) -> str:
        return (text_block.window_text() or "").strip()

    def _read_ocr(self, text_block) -> str:
        try:
            import pytesseract
            from PIL import ImageGrab
        except ImportError as exc:
            raise ImportError(
                "OCR fallback needs pytesseract and Pillow. "
                "Install Tesseract OCR and: pip install pytesseract"
            ) from exc

        rect = text_block.rectangle()
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        return (pytesseract.image_to_string(image) or "").strip()

    def _read_current(self, text_block) -> str:
        reader = self._read_ocr if self.method == "ocr" else self._read_uia
        raw = reader(text_block)
        return (raw if isinstance(raw, str) else "") or ""

    def seed_baseline(self, text_block) -> str:
        """Seed last-block from current panel without recording (avoid dumping buffer)."""
        current = self._read_current(text_block)
        self._last_block = current
        self._seeded = True
        if self._stabilizer is not None and current:
            self._stabilizer.mark_seen_from_panel(current)
        return current

    def _apply_commit(self, action: str, segment: str) -> None:
        segment = normalize_segment(segment)
        if not segment:
            return
        now = time.time()
        if action == "replace_last":
            # Prefer replacing the most similar recent spoken line (not session breaks).
            best_i = -1
            best_score = 0.0
            for i in range(len(self.segments) - 1, -1, -1):
                if self.segments[i] == _SESSION_BREAK:
                    continue
                score = similarity_ratio(segment, self.segments[i])
                if score > best_score:
                    best_score = score
                    best_i = i
                if i < len(self.segments) - 8:
                    break
            if best_i >= 0 and best_score >= self.similarity:
                self.segments[best_i] = segment
                if best_i < len(self._segment_times):
                    self._segment_times[best_i] = now
                if self.on_segment:
                    self.on_segment(segment)
                return
            action = "append"

        if _DOUBT_BREAK_RE.search(segment):
            if not self.segments or self.segments[-1] != _SESSION_BREAK:
                self.segments.append(_SESSION_BREAK)
                self._segment_times.append(now)
        self.segments.append(segment)
        self._segment_times.append(now)
        if self.on_segment:
            self.on_segment(segment)

    def _record(self, segment: str) -> None:
        """Direct append (tests / idle helpers). Prefer stabilizer path in poll_once."""
        self._apply_commit("append", segment)

    def poll_once(self, text_block) -> bool:
        """Read panel; commit stable sentences. Returns True if anything new was saved."""
        if not self._seeded:
            self.seed_baseline(text_block)
            return False
        current = self._read_current(text_block)
        if not current:
            return False

        # Keep delta helper accurate for diagnostics / fallbacks.
        _ = extract_caption_delta(self._last_block, current)
        self._last_block = current

        assert self._stabilizer is not None
        commits = self._stabilizer.observe_panel(current)
        if not commits:
            return False
        for action, sentence in commits:
            self._apply_commit(action, sentence)
        return True

    def flush_pending(self) -> None:
        """Commit trailing panel text on stop (SaveLC exit flush)."""
        if not self._last_block or self._stabilizer is None:
            return
        for action, sentence in self._stabilizer.flush_trailing(self._last_block):
            self._apply_commit(action, sentence)

    def run(
        self,
        *,
        max_seconds: float | None = None,
        idle_seconds: float | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[str]:
        """Block until stop_event, idle silence, max_seconds, or connection loss."""
        # Background threads must init COM or pywinauto UIA often hangs forever.
        com_inited = False
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_inited = True
        except Exception:
            pass

        try:
            text_block = self._connect_uia()
            seeded = self.seed_baseline(text_block)
            if self.on_ready:
                try:
                    self.on_ready(len(seeded))
                except Exception:
                    pass
            if self.on_heartbeat:
                try:
                    self.on_heartbeat(0, 0.0)
                except Exception:
                    pass

            started = time.monotonic()
            deadline = started + max_seconds if max_seconds else None
            last_heartbeat = started
            last_new_segment_at: float | None = None
            failures = 0

            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    break
                if (
                    idle_seconds is not None
                    and idle_seconds > 0
                    and last_new_segment_at is not None
                    and time.monotonic() - last_new_segment_at >= idle_seconds
                ):
                    break
                try:
                    if self.poll_once(text_block):
                        failures = 0
                        last_new_segment_at = time.monotonic()
                except Exception as exc:
                    failures += 1
                    if failures >= 3:
                        print(f"\nReconnecting to Live Captions ({exc})…", file=sys.stderr, flush=True)
                        try:
                            text_block = self._connect_uia()
                            self.seed_baseline(text_block)
                            failures = 0
                            print("Reconnected.", flush=True)
                            continue
                        except Exception as reconnect_exc:
                            print(f"Reconnect failed: {reconnect_exc}", file=sys.stderr)
                            break
                    time.sleep(min(2.0, self.poll_interval * 4))
                    continue

                now = time.monotonic()
                if now - last_heartbeat >= _HEARTBEAT_SEC:
                    idle_for = (
                        now - last_new_segment_at if last_new_segment_at is not None else now - started
                    )
                    if self.on_heartbeat:
                        self.on_heartbeat(len(self.segments), idle_for)
                    print(
                        f"… still listening ({len(self.segments)} segments, quiet {idle_for:.0f}s) — Ctrl+C to stop",
                        flush=True,
                    )
                    last_heartbeat = now

                time.sleep(self.poll_interval)

            self.flush_pending()
            return self.segments
        finally:
            if com_inited:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def save(self, path: Path | None = None) -> Path:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = TRANSCRIPTS_DIR / f"live_captions_{stamp}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for i, seg in enumerate(self.segments):
            if seg == _SESSION_BREAK or not self.timestamps:
                lines.append(seg)
                continue
            ts = self._segment_times[i] if i < len(self._segment_times) else time.time()
            stamp = time.strftime("%H:%M:%S", time.localtime(ts))
            lines.append(f"[{stamp}] {seg}")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def ensure_windows() -> None:
    if platform.system() != "Windows":
        print("Live Captions scraping only works on Windows 11.", file=sys.stderr)
        sys.exit(1)
