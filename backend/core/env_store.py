"""Safe read/write for LLM-related keys in repo .env."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.paths import ROOT

ENV_PATH = ROOT / ".env"
ENV_BACKUP_PATH = ROOT / ".env.bak"

# Env var names allowed via PATCH (no arbitrary injection).
ALLOWED_ENV_KEYS = frozenset(
    {
        "LLM_CLOUD_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "CEREBRAS_API_KEY",
        "MISTRAL_API_KEY",
        "GITHUB_TOKEN",
        "LLM_OPENROUTER_API_KEY",
        "LLM_ANTHROPIC_API_KEY",
        "NIM_API_KEY",
        "LLM_API_KEY",
        "TAVILY_API_KEY",
        "LLM_ROUTE_PROFILE",
        "OLLAMA_URL",
        "LMSTUDIO_URL",
        "OLLAMA_NATIVE_URL",
        "OLLAMA_MODEL",
        "LLM_PROVIDER",
        "OLLAMA_ENABLED",
    }
)

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def env_file_path() -> Path:
    return ENV_PATH


def read_env_lines() -> list[str]:
    if not ENV_PATH.is_file():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _quote_env_value(value: str) -> str:
    if not value:
        return '""'
    if any(c in value for c in " \t#\"'\\"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def patch_env(updates: dict[str, str]) -> list[str]:
    """Merge updates into .env; empty string removes the key. Returns keys written."""
    filtered: dict[str, str] = {}
    for key, value in updates.items():
        upper = key.strip().upper()
        if upper not in ALLOWED_ENV_KEYS:
            continue
        filtered[upper] = value

    if not filtered:
        return []

    lines = read_env_lines()
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        m = _ENV_LINE.match(line)
        if not m:
            out.append(line)
            continue
        name = m.group(1)
        if name not in filtered:
            out.append(line)
            continue
        seen.add(name)
        new_val = filtered[name]
        if new_val == "":
            continue
        out.append(f"{name}={_quote_env_value(new_val)}")

    for name, new_val in filtered.items():
        if name in seen or new_val == "":
            continue
        out.append(f"{name}={_quote_env_value(new_val)}")

    if ENV_PATH.is_file():
        shutil.copy2(ENV_PATH, ENV_BACKUP_PATH)

    text = "\n".join(out)
    if out:
        text += "\n"

    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, ENV_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    reload_settings(filtered)
    return list(filtered.keys())


def reload_settings(updated: dict[str, str] | None = None) -> None:
    """Clear settings cache and sync os.environ for hot reload."""
    from backend.config import get_settings

    if updated:
        for key, value in updated.items():
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    get_settings.cache_clear()
