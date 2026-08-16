"""Minimal Tk chat UI for voice agent (textbox + history).

Includes Jarvis | Normal TTS mode toggle; mode also via `/voice` in chat.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import scrolledtext
from typing import TYPE_CHECKING

log = logging.getLogger("desktop_tracker.voice_agent")

if TYPE_CHECKING:
    from backend.behavior.voice_agent.agent import VoiceAgent

_ui_lock = threading.Lock()
_root: tk.Tk | None = None


def open_chat_window(agent: "VoiceAgent") -> None:
    """Open or focus the chat window on a dedicated Tk thread."""

    def runner() -> None:
        global _root
        with _ui_lock:
            if _root is not None:
                try:
                    _root.lift()
                    _root.focus_force()
                    return
                except Exception:
                    _root = None

        from backend.behavior.voice_agent.io_speech import get_tts_mode, set_tts_mode, speak

        root = tk.Tk()
        _root = root
        root.title("CALT Voice Agent")
        root.geometry("420x520")
        root.configure(bg="#0f1115")

        def mode_status_text() -> str:
            mode = get_tts_mode()
            label = "Jarvis" if mode == "jarvis" else "Normal"
            return f"Mode: {label} · /brief · /voice jarvis|normal"

        status = tk.Label(
            root,
            text=mode_status_text(),
            bg="#0f1115",
            fg="#9ca3af",
            font=("Segoe UI", 9),
        )
        status.pack(fill="x", padx=10, pady=(10, 4))

        mode_row = tk.Frame(root, bg="#0f1115")
        mode_row.pack(fill="x", padx=10, pady=(0, 4))

        log_box = scrolledtext.ScrolledText(
            root,
            height=18,
            bg="#161b22",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            font=("Consolas", 10),
            wrap="word",
        )
        log_box.pack(fill="both", expand=True, padx=10, pady=6)
        log_box.configure(state="disabled")

        row = tk.Frame(root, bg="#0f1115")
        row.pack(fill="x", padx=10, pady=(0, 10))
        entry = tk.Entry(row, bg="#1f2937", fg="#f9fafb", insertbackground="#f9fafb", font=("Segoe UI", 11))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        busy = {"v": False}
        mode_btns: dict[str, tk.Button] = {}

        def refresh_mode_ui() -> None:
            mode = get_tts_mode()
            status.configure(text=mode_status_text())
            for key, btn in mode_btns.items():
                active = key == mode
                btn.configure(
                    bg="#1d4ed8" if active else "#374151",
                    relief="sunken" if active else "raised",
                )

        def append(role: str, text: str) -> None:
            log_box.configure(state="normal")
            log_box.insert("end", f"{role}: {text}\n\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        from backend.behavior.voice_agent import announce as dialogue_announce

        chat_seq = {"v": 0}

        def on_agent_reply(text: str) -> None:
            # Paint reply on the Tk thread and wait so TTS starts after text is visible.
            done = threading.Event()

            def paint() -> None:
                try:
                    append("Agent", text)
                    root.update_idletasks()
                finally:
                    done.set()

            root.after(0, paint)
            done.wait(timeout=2.0)

        def on_canned_dialogue(text: str) -> None:
            """Same-process canned speak (morning brief, /brief, etc.)."""
            done = threading.Event()

            def paint() -> None:
                try:
                    append("Jarvis", text)
                    chat_seq["v"] = dialogue_announce.feed_seq()
                    root.update_idletasks()
                finally:
                    done.set()

            try:
                root.after(0, paint)
                done.wait(timeout=2.0)
            except Exception:  # noqa: BLE001
                pass

        # Catch-up: lines spoken while chat was closed (API / tracker)
        for prior in dialogue_announce.recent_lines(limit=8):
            append("Jarvis", prior)
        chat_seq["v"] = dialogue_announce.feed_seq()
        dialogue_announce.register_ui_callback(on_canned_dialogue)

        def poll_cross_process_dialogue() -> None:
            """API process may speak while chat runs in tracker — pick up feed."""
            try:
                pending = dialogue_announce.pending_lines_for_ui(since_seq=chat_seq["v"])
                for row in pending:
                    t = str(row.get("text") or "").strip()
                    if t:
                        append("Jarvis", t)
                    try:
                        chat_seq["v"] = max(chat_seq["v"], int(row.get("seq") or 0))
                    except (TypeError, ValueError):
                        pass
            except Exception as exc:  # noqa: BLE001
                log.debug("dialogue poll: %s", exc)
            try:
                root.after(1200, poll_cross_process_dialogue)
            except Exception:
                pass

        root.after(1200, poll_cross_process_dialogue)

        agent.on_reply = on_agent_reply

        def switch_mode(mode: str, *, sample: bool = True) -> None:
            if busy["v"]:
                return
            try:
                set_tts_mode(mode)
            except ValueError:
                return
            refresh_mode_ui()
            label = "Jarvis" if mode == "jarvis" else "Normal"
            append("System", f"Voice → {label}")
            if sample:
                phrase = "Jarvis mode." if mode == "jarvis" else "Normal voice."

                def work() -> None:
                    try:
                        speak(phrase)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("mode sample failed: %s", exc)

                threading.Thread(target=work, name="voice-mode-sample", daemon=True).start()

        mode_btns["jarvis"] = tk.Button(
            mode_row,
            text="Jarvis",
            command=lambda: switch_mode("jarvis"),
            bg="#374151",
            fg="#fff",
            width=10,
        )
        mode_btns["jarvis"].pack(side="left", padx=(0, 6))
        mode_btns["normal"] = tk.Button(
            mode_row,
            text="Normal",
            command=lambda: switch_mode("normal"),
            bg="#374151",
            fg="#fff",
            width=10,
        )
        mode_btns["normal"].pack(side="left")
        refresh_mode_ui()

        def submit(_: object = None) -> None:
            if busy["v"]:
                return
            text = entry.get().strip()
            if not text:
                return
            entry.delete(0, "end")
            append("You", text)
            busy["v"] = True
            status.configure(text="Thinking…")

            def work() -> None:
                from backend.behavior.voice_agent.session import voice_session

                try:
                    with voice_session(user_id=agent.user_id, trigger="chat_text"):
                        agent.handle_utterance(text, say=True)
                finally:
                    def done() -> None:
                        busy["v"] = False
                        refresh_mode_ui()

                    root.after(0, done)

            threading.Thread(target=work, name="voice-agent-chat", daemon=True).start()

        def listen() -> None:
            if busy["v"]:
                return
            busy["v"] = True
            status.configure(text="Listening…")

            def work() -> None:
                from backend.behavior.voice_agent.io_speech import listen_once
                from backend.behavior.voice_agent.session import voice_session

                try:
                    with voice_session(user_id=agent.user_id, trigger="chat_mic"):
                        heard = listen_once()
                except Exception:
                    heard = ""

                def after() -> None:
                    busy["v"] = False
                    if not heard:
                        status.configure(text="No speech — type instead")
                        refresh_mode_ui()
                        return
                    append("You", heard)
                    status.configure(text="Thinking…")
                    busy["v"] = True

                    def think() -> None:
                        from backend.behavior.voice_agent.session import voice_session

                        try:
                            with voice_session(user_id=agent.user_id, trigger="chat_mic_think"):
                                agent.handle_utterance(heard, say=True)
                        finally:
                            root.after(
                                0,
                                lambda: (
                                    busy.update(v=False),
                                    refresh_mode_ui(),
                                ),
                            )

                    threading.Thread(target=think, daemon=True).start()

                root.after(0, after)

            threading.Thread(target=work, name="voice-agent-listen", daemon=True).start()

        tk.Button(row, text="Send", command=submit, bg="#374151", fg="#fff").pack(side="left", padx=(0, 4))
        tk.Button(row, text="Mic", command=listen, bg="#065f46", fg="#fff").pack(side="left")
        entry.bind("<Return>", submit)
        entry.focus_set()

        def on_close() -> None:
            global _root
            agent.on_reply = None
            try:
                from backend.behavior.voice_agent import announce as dialogue_announce

                dialogue_announce.register_ui_callback(None)
            except Exception:  # noqa: BLE001
                pass
            _root = None
            try:
                from backend.behavior.voice_agent.session import release_session_resources

                release_session_resources()
            except Exception as exc:  # noqa: BLE001
                log.debug("release on chat close: %s", exc)
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        root.mainloop()

    threading.Thread(target=runner, name="voice-agent-ui", daemon=True).start()
