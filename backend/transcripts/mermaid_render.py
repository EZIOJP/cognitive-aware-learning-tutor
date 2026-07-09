"""Render mermaid source to PNG at export time (optional mmdc / npx fallback)."""

from __future__ import annotations

import base64
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_CACHE: dict[str, bytes] = {}


def render_mermaid_png(source: str, *, timeout_sec: float = 45.0) -> bytes | None:
    """Return PNG bytes for mermaid source, or None if rendering is unavailable."""
    text = (source or "").strip()
    if not text:
        return None
    if text in _CACHE:
        return _CACHE[text]

    mmdc = shutil.which("mmdc")
    with tempfile.TemporaryDirectory(prefix="mermaid_export_") as tmp:
        inp = Path(tmp) / "diagram.mmd"
        out = Path(tmp) / "diagram.png"
        inp.write_text(text, encoding="utf-8")
        if mmdc:
            cmd = [mmdc, "-i", str(inp), "-o", str(out), "-b", "transparent"]
        else:
            cmd = [
                "npx",
                "--yes",
                "@mermaid-js/mermaid-cli",
                "-i",
                str(inp),
                "-o",
                str(out),
                "-b",
                "transparent",
            ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=timeout_sec,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            log.debug("Mermaid render skipped: %s", exc)
            return None
        if not out.is_file():
            return None
        data = out.read_bytes()
        _CACHE[text] = data
        return data


def mermaid_png_data_uri(source: str) -> str | None:
    png = render_mermaid_png(source)
    if not png:
        return None
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}"
