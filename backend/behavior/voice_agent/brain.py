"""LLM call + tool line parsing for voice agent."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from backend.behavior.voice_agent.tools import tools_prompt_block

log = logging.getLogger("desktop_tracker.voice_agent")

# Voice sessions: do not pin Ollama weights after the turn (VRAM / thermal).
_VOICE_KEEP_ALIVE = 0

_TOOL_RE = re.compile(
    r"^\s*TOOL\s+([a-z0-9_]+)\s+(\{.*\})\s*$",
    re.IGNORECASE | re.DOTALL,
)
_TOOL_BARE = re.compile(r"^\s*TOOL\s+([a-z0-9_]+)\s*$", re.IGNORECASE)


def parse_tool_line(text: str) -> tuple[str, dict[str, Any]] | None:
    """Extract first TOOL name {json} from model output."""
    if not text:
        return None
    for line in text.strip().splitlines():
        line = line.strip()
        m = _TOOL_RE.match(line)
        if m:
            name = m.group(1).lower()
            try:
                args = json.loads(m.group(2))
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            return name, args
        m2 = _TOOL_BARE.match(line)
        if m2:
            return m2.group(1).lower(), {}
    # whole blob is a tool line
    m = _TOOL_RE.match(text.strip())
    if m:
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            args = {}
        return m.group(1).lower(), args if isinstance(args, dict) else {}
    return None


def strip_tool_lines(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        if _TOOL_RE.match(line.strip()) or _TOOL_BARE.match(line.strip()):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def build_system_prompt(*, facts: str, gate_line: str) -> str:
    return (
        "You are CALT Voice Agent — a calm, capable butler-style assistant on the user's Windows PC "
        "(Jarvis-adjacent: dry wit, composed, never theatrical).\n"
        "Be talkative and reactive in free chat: acknowledge what the user just said or did, "
        "then help — still prefer tools + short spoken answers over essays.\n"
        "Ritual lines (morning brief, bible/plan praise, gate blocks) are spoken by the system "
        "separately with canned dialogue — do not re-announce those rituals unless asked.\n"
        "Speak briefly. Prefer short spoken-friendly sentences. Address the user as 'sir' sparingly "
        "(at most once every few turns, never every reply). Do not lengthen answers for style.\n"
        "Chat commands: /brief forces a canned morning-style brief (you won't handle that — system does).\n"
        f"Gate: {gate_line}\n"
        f"Known facts:\n{facts or '(none)'}\n\n"
        f"{tools_prompt_block()}\n"
        "If the user asks something you can do with a tool, emit a TOOL line first. "
        "Do not pretend you locked the PC without a tool."
    )


_BRAIN_OFFLINE_HINT = (
    "Start LM Studio on :1234, or set LLM_ROUTE_PROFILE=hybrid-free / openrouter "
    "(OpenRouter key in .env), then restart the tracker."
)


def _build_prompt(
    *,
    user_text: str,
    history: list[dict[str, str]],
    facts: str,
    gate_line: str,
) -> tuple[str, str]:
    hist = ""
    for t in history[-8:]:
        hist += f"{t['role'].upper()}: {t['content']}\n"
    prompt = f"{hist}USER: {user_text}\nASSISTANT:"
    system = build_system_prompt(facts=facts, gate_line=gate_line)
    return prompt, system


def _iter_ollama_native_stream(
    prompt: str,
    *,
    system_prompt: str,
    base_url: str,
    model: str,
    timeout: float = 90.0,
) -> Iterator[str]:
    """Yield response tokens from Ollama /api/generate with keep_alive=0."""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": True,
        "keep_alive": _VOICE_KEEP_ALIVE,
    }
    url = f"{base_url.rstrip('/')}/api/generate"
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, json=payload) as res:
            res.raise_for_status()
            for line in res.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = data.get("response") or ""
                if piece:
                    yield piece
                if data.get("done"):
                    break


def _iter_openai_compat_stream(
    prompt: str,
    *,
    system_prompt: str,
    base_url: str,
    model: str,
    api_key: str | None = None,
    timeout: float = 90.0,
) -> Iterator[str]:
    """Yield tokens from OpenAI-compatible chat completions (LM Studio, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages, "stream": True}
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, json=payload, headers=headers) as res:
            res.raise_for_status()
            for line in res.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    if line == "[DONE]":
                        break
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content") or ""
                if piece:
                    yield piece


def try_stream_local(
    prompt: str,
    *,
    system_prompt: str,
    timeout: float = 90.0,
) -> Iterator[str] | None:
    """Return a token iterator for local Ollama/LM Studio, or None if unavailable."""
    from backend.core.ollama_client import resolve_llm_options

    opts = resolve_llm_options()
    provider = (opts.provider or "").lower()
    base = (opts.base_url or "").rstrip("/")
    model = (opts.model or "").strip()
    if not base or not model:
        return None

    def _ollama() -> Iterator[str]:
        yield from _iter_ollama_native_stream(
            prompt,
            system_prompt=system_prompt,
            base_url=base,
            model=model,
            timeout=timeout,
        )

    def _openai() -> Iterator[str]:
        yield from _iter_openai_compat_stream(
            prompt,
            system_prompt=system_prompt,
            base_url=base,
            model=model,
            api_key=opts.api_key,
            timeout=timeout,
        )

    if provider == "ollama":
        return _ollama()
    if provider in ("lmstudio", "openai"):
        # LM Studio / local OpenAI-compat — stream when possible
        return _openai()
    return None


def call_brain_stream(
    *,
    user_text: str,
    history: list[dict[str, str]],
    facts: str,
    gate_line: str,
    on_token: Callable[[str], None] | None = None,
) -> tuple[str, str | None]:
    """Stream local LLM when possible; else full `call_brain`. Invokes on_token per piece.

    Returns (full_text, error). On stream failure, falls back to non-streaming path.
    """
    prompt, system = _build_prompt(
        user_text=user_text, history=history, facts=facts, gate_line=gate_line
    )
    stream = try_stream_local(prompt, system_prompt=system, timeout=90.0)
    streamed_any = False
    if stream is not None:
        parts: list[str] = []
        try:
            for piece in stream:
                streamed_any = True
                parts.append(piece)
                if on_token:
                    try:
                        on_token(piece)
                    except Exception as exc:  # noqa: BLE001
                        log.debug("on_token error: %s", exc)
            text = "".join(parts).strip()
            if text:
                return text, None
            log.info("voice stream empty — falling back to call_brain")
        except Exception as exc:  # noqa: BLE001
            log.warning("voice stream failed (%s) — falling back to call_brain", exc)
            partial = "".join(parts).strip()
            if partial:
                # Already fed on_token; do not re-speak via fallback
                return partial, None

    text, err = call_brain(
        user_text=user_text, history=history, facts=facts, gate_line=gate_line
    )
    if text and on_token and not streamed_any:
        try:
            on_token(text)
        except Exception as exc:  # noqa: BLE001
            log.debug("on_token (fallback) error: %s", exc)
    return text, err


def call_brain(
    *,
    user_text: str,
    history: list[dict[str, str]],
    facts: str,
    gate_line: str,
) -> tuple[str, str | None]:
    """Returns (text, error_message). text empty when failed."""
    from backend.config import get_settings
    from backend.core.llm_gateway import llm_complete
    from backend.core.ollama_client import LlmOptions, ollama_generate

    prompt, system = _build_prompt(
        user_text=user_text, history=history, facts=facts, gate_line=gate_line
    )

    local_err: str | None = None
    try:
        out = ollama_generate(
            prompt,
            system_prompt=system,
            task="voice_agent",
            timeout=90.0,
        )
        text = (out or "").strip()
        if text:
            return text, None
        local_err = "No reply from AI handler (model empty or all providers failed)."
    except TypeError as exc:
        log.warning("voice_agent brain TypeError: %s", exc)
        local_err = str(exc)
    except Exception as exc:  # noqa: BLE001
        log.warning("voice_agent brain failed: %s", exc)
        local_err = str(exc)

    or_key = (get_settings().llm_openrouter_api_key or "").strip()
    if or_key:
        try:
            result = llm_complete(
                prompt,
                system_prompt=system,
                task="voice_agent",
                timeout=90.0,
                route_profile="openrouter",
            )
            text = (result.text or "").strip()
            if text:
                log.info("voice_agent brain recovered via openrouter profile")
                return text, None
        except Exception as exc:  # noqa: BLE001
            log.warning("voice_agent openrouter profile failed: %s", exc)

        try:
            result = llm_complete(
                prompt,
                system_prompt=system,
                task="voice_agent",
                timeout=90.0,
                llm=LlmOptions(
                    provider="openrouter",
                    base_url="https://openrouter.ai/api/v1",
                    model="openai/gpt-4o-mini",
                    api_key=or_key,
                ),
            )
            text = (result.text or "").strip()
            if text:
                log.info("voice_agent brain recovered via direct openrouter")
                return text, None
        except Exception as exc:  # noqa: BLE001
            log.warning("voice_agent openrouter direct failed: %s", exc)

    detail = local_err or "No reply from AI handler."
    return "", f"{detail} {_BRAIN_OFFLINE_HINT}"