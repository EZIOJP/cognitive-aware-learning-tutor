"""Voice agent orchestrator — safe to run beside tracker poll loop."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from backend.behavior.voice_agent import memory as mem
from backend.behavior.voice_agent.brain import (
    call_brain_stream,
    parse_tool_line,
    strip_tool_lines,
)
from backend.behavior.voice_agent.chunker import SentenceStreamChunker
from backend.behavior.voice_agent.confirm import ConfirmGate
from backend.behavior.voice_agent.io_speech import speak
from backend.behavior.voice_agent.tools import confirm_prompt, execute_tool, is_risky

log = logging.getLogger("desktop_tracker.voice_agent")


class _StreamSpeakGate:
    """Buffer stream tokens; mute TOOL lines. Speak only after UI via flush_speak()."""

    def __init__(self, speak_fn: Callable[[str], None]) -> None:
        self._speak = speak_fn
        self._chunker = SentenceStreamChunker()
        self._raw = ""
        self._mode = "hold"  # hold | speak | mute
        self._pending: list[str] = []
        self.spoken = False

    def feed(self, token: str) -> None:
        if not token or self._mode == "mute":
            if token:
                self._raw += token
            return
        self._raw += token
        if self._mode == "hold":
            s = self._raw.lstrip()
            if not s:
                return
            up = s.upper()
            if up.startswith("TOOL"):
                self._mode = "mute"
                return
            # Prefix of TOOL — keep holding
            if "TOOL".startswith(up) and len(up) < 4:
                return
            self._mode = "speak"
            self._pending.extend(self._chunker.feed(self._raw))
            return
        self._pending.extend(self._chunker.feed(token))

    def finish(self) -> str:
        if self._mode == "speak":
            self._pending.extend(self._chunker.flush())
        return self._raw.strip()

    def flush_speak(self) -> None:
        """Speak buffered sentences (call only after the reply is shown in UI)."""
        for sent in self._pending:
            try:
                self._speak(sent)
                self.spoken = True
            except Exception as exc:  # noqa: BLE001
                log.warning("speak failed: %s", exc)
        self._pending.clear()


class VoiceAgent:
    def __init__(self, user_id: int) -> None:
        self.user_id = int(user_id)
        self.confirm = ConfirmGate()
        self._lock = threading.Lock()
        self.on_reply: Callable[[str], None] | None = None

    def _emit(
        self,
        text: str,
        *,
        say: bool = True,
        gate: _StreamSpeakGate | None = None,
    ) -> str:
        """Show reply text first, then TTS. Speak failures must not hide the reply."""
        text = (text or "").strip()
        if not text:
            return ""
        if self.on_reply:
            try:
                self.on_reply(text)
            except Exception:  # noqa: BLE001
                pass
        if say:
            try:
                if gate is not None and gate._mode == "speak":
                    gate.flush_speak()
                    if not gate.spoken:
                        speak(text)
                else:
                    speak(text)
            except Exception as exc:  # noqa: BLE001
                log.warning("speak failed: %s", exc)
        return text

    def _speak_only(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        try:
            speak(text)
        except Exception as exc:  # noqa: BLE001
            log.warning("speak failed: %s", exc)

    def _gate_line(self) -> str:
        try:
            from backend.behavior.distraction_gate import compute_distraction_gate
            from backend.db.session import SessionLocal

            db = SessionLocal()
            try:
                g = compute_distraction_gate(db, self.user_id)
            finally:
                db.close()
            m = g.get("morning") or {}
            return (
                f"locked={g.get('locked')} morning={m.get('next')} "
                f"productive={g.get('productive_minutes')}/{g.get('daily_goal_minutes')}"
            )
        except Exception:  # noqa: BLE001
            return "gate=unknown"

    def handle_utterance(self, text: str, *, say: bool = True) -> str:
        text = (text or "").strip()
        if not text:
            return self._emit("I didn't catch that.", say=say)

        with self._lock:
            # Slash: /voice … · /brief (canned morning brief, no LLM)
            voice_reply = self._handle_slash_command(text, say=say)
            if voice_reply is not None:
                return voice_reply

            # Confirm flow first
            def _exec(name: str, args: dict[str, Any]) -> str:
                return execute_tool(self.user_id, name, args)

            reply, handled = self.confirm.resolve(text, _exec)
            if handled and reply is not None:
                mem.append_turn(self.user_id, "user", text)
                mem.append_turn(self.user_id, "assistant", reply)
                return self._emit(reply, say=say)

            mem.append_turn(self.user_id, "user", text)
            history = mem.load_turns(self.user_id)
            facts = mem.memory_get(self.user_id)
            gate = self._gate_line()

            gate_speak: _StreamSpeakGate | None = None
            if say:
                gate_speak = _StreamSpeakGate(self._speak_only)

            raw, err = call_brain_stream(
                user_text=text,
                history=history[:-1],
                facts=facts,
                gate_line=gate,
                on_token=gate_speak.feed if gate_speak else None,
            )
            if gate_speak:
                raw = gate_speak.finish() or raw

            if not raw:
                msg = (
                    f"Brain offline — {err}"
                    if err
                    else "Brain offline — check LM Studio or AI Control Center."
                )
                mem.append_turn(self.user_id, "assistant", msg)
                return self._emit(msg, say=say)

            tool = parse_tool_line(raw)
            if tool:
                name, args = tool
                if is_risky(name):
                    prompt = confirm_prompt(name)
                    self.confirm.arm(name, args, prompt)
                    msg = f"{prompt} Say yes or no."
                    mem.append_turn(self.user_id, "assistant", msg)
                    return self._emit(msg, say=say)
                try:
                    result = execute_tool(self.user_id, name, args)
                except Exception as exc:  # noqa: BLE001
                    result = f"Tool error: {exc}"
                # Second pass: stream summarize when possible
                follow_gate: _StreamSpeakGate | None = None
                if say:
                    follow_gate = _StreamSpeakGate(self._speak_only)
                follow, ferr = call_brain_stream(
                    user_text=(
                        f"Tool {name} returned: {result}\n"
                        "Give a short spoken answer to the user."
                    ),
                    history=mem.load_turns(self.user_id),
                    facts=facts,
                    gate_line=gate,
                    on_token=follow_gate.feed if follow_gate else None,
                )
                if follow_gate:
                    follow = follow_gate.finish() or follow
                msg = strip_tool_lines(follow) or result
                if not follow and ferr:
                    msg = result
                mem.append_turn(self.user_id, "assistant", msg)
                # Text in UI first, then deferred sentence TTS from stream buffer
                return self._emit(msg, say=say, gate=follow_gate)

            msg = strip_tool_lines(raw) or raw
            mem.append_turn(self.user_id, "assistant", msg)
            # Text in UI first, then deferred sentence TTS from stream buffer
            return self._emit(msg, say=say, gate=gate_speak)

    def _handle_slash_command(self, text: str, *, say: bool) -> str | None:
        """Parse `/voice`, `/brief`. None if not a slash cmd."""
        from backend.behavior.voice_agent.io_speech import get_tts_mode, set_tts_mode

        parts = text.split()
        if not parts:
            return None
        cmd = parts[0].lower()

        if cmd in ("/brief", "/briefme"):
            from backend.behavior.voice_agent.morning_brief import force_brief

            mem.append_turn(self.user_id, "user", text)
            lines = force_brief(self.user_id)
            msg = " ".join(lines) if lines else "Brief unavailable."
            mem.append_turn(self.user_id, "assistant", msg)
            # TTS already started by force_brief — show text only (no double-speak)
            return self._emit(msg, say=False)

        if cmd != "/voice":
            return None

        arg = parts[1].lower() if len(parts) > 1 else ""
        if not arg:
            mode = get_tts_mode()
            msg = f"Voice mode: {mode}."
            mem.append_turn(self.user_id, "user", text)
            mem.append_turn(self.user_id, "assistant", msg)
            return self._emit(msg, say=say)

        if arg in ("jarvis", "normal"):
            set_tts_mode(arg)
            sample = "Jarvis mode." if arg == "jarvis" else "Normal voice."
            msg = f"Switched to {arg}."
            mem.append_turn(self.user_id, "user", text)
            mem.append_turn(self.user_id, "assistant", msg)
            out = self._emit(msg, say=False)
            if say:
                try:
                    speak(sample)
                except Exception as exc:  # noqa: BLE001
                    log.warning("voice sample failed: %s", exc)
            return out

        msg = "Usage: /voice [jarvis|normal] · /brief"
        mem.append_turn(self.user_id, "user", text)
        mem.append_turn(self.user_id, "assistant", msg)
        return self._emit(msg, say=say)

    def _handle_voice_command(self, text: str, *, say: bool) -> str | None:
        """Backward-compatible alias for slash commands."""
        return self._handle_slash_command(text, say=say)
