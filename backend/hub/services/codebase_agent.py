"""Read-only codebase index for the Project Agent (Gemma + Cursor pair)."""

from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_SKIP_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".cursor",
        "refernces",
        "transcript-notes-studio",
        "data",
        "public",
    }
)

_SCAN_ROOTS = ("src", "backend", "scripts", "docs", "alembic")
_TEXT_EXTENSIONS = frozenset(
    {".py", ".tsx", ".ts", ".jsx", ".js", ".css", ".md", ".bat", ".sh", ".json", ".mdc"}
)
_MAX_FILE_BYTES = 48_000
_MAX_EXCERPT = 4_500
_MAX_FILES_IN_TREE = 400

_ROUTE_RE = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)')
_PATH_ROUTE_RE = re.compile(r'path:\s*["\']([^"\']+)["\']')
_CLASSNAME_RE = re.compile(r'className\s*=\s*["\']([^"\']+)["\']')
# Letter-first class names only; skips `.5rem`-style false positives in minified CSS.
_CSS_CLASS_RE = re.compile(r"\.([a-zA-Z][\w-]*)")
# Comment markers only — omit XXX (too many false positives in code/hex).
_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b\s*:?\s+(.{0,120})", re.IGNORECASE)

_snapshot_cache: dict[str, Any] | None = None
_snapshot_at: float = 0.0
_SNAPSHOT_TTL_SEC = 120.0


def _is_skipped(path: Path) -> bool:
    return any(part in _SKIP_DIR_NAMES for part in path.parts)


def _iter_project_files() -> list[Path]:
    files: list[Path] = []
    for root_name in _SCAN_ROOTS:
        base = ROOT / root_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if _is_skipped(path.relative_to(ROOT)):
                continue
            if path.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            if path.stat().st_size > _MAX_FILE_BYTES * 4:
                continue
            files.append(path)
            if len(files) >= _MAX_FILES_IN_TREE * 3:
                break
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _extract_frontend_routes() -> list[str]:
    routes: list[str] = []
    for pattern in (ROOT / "src" / "app" / "App.tsx", ROOT / "src" / "plugins" / "core_plugins.tsx"):
        if not pattern.is_file():
            continue
        text = pattern.read_text(encoding="utf-8", errors="replace")
        for m in _PATH_ROUTE_RE.finditer(text):
            routes.append(m.group(1))
        for m in re.finditer(r'path="([^"]+)"', text):
            routes.append(m.group(1))
    return sorted(set(routes))


def _extract_api_routes() -> list[str]:
    routes: list[str] = []
    backend = ROOT / "backend"
    if not backend.is_dir():
        return routes
    for path in backend.rglob("router.py"):
        if _is_skipped(path.relative_to(ROOT)):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        prefix_m = re.search(r'APIRouter\(\s*prefix\s*=\s*["\']([^"\']+)', text)
        prefix = prefix_m.group(1) if prefix_m else ""
        for m in _ROUTE_RE.finditer(text):
            full = f"{prefix}{m.group(2)}"
            routes.append(full)
    return sorted(set(routes))[:80]


def _count_css_classes(files: list[Path]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for path in files:
        if path.suffix.lower() != ".css" and path.suffix.lower() not in {".tsx", ".jsx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix.lower() == ".css":
            for m in _CSS_CLASS_RE.finditer(text):
                name = m.group(1)
                if name not in ("hover", "focus", "active", "first", "last"):
                    counter[name] += 1
        else:
            for m in _CLASSNAME_RE.finditer(text):
                for part in m.group(1).split():
                    if part and not part.startswith("{"):
                        counter[part] += 1
    return [{"class": k, "count": v} for k, v in counter.most_common(40)]


def _scan_todos(files: list[Path], limit: int = 20) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = _TODO_RE.search(line)
            if m:
                hits.append(
                    {
                        "file": _rel(path),
                        "line": str(i),
                        "tag": m.group(1).upper(),
                        "text": m.group(2).strip()[:100],
                    }
                )
            if len(hits) >= limit:
                return hits
    return hits


def _pipeline_status() -> dict[str, Any]:
    scripts = ROOT / "scripts"
    transcripts_dir = ROOT / "data" / "transcripts"
    notes_dir = ROOT / "data" / "notes"
    transcript_count = (
        len(list(transcripts_dir.glob("live_captions_*.txt"))) if transcripts_dir.is_dir() else 0
    )
    note_count = len(list(notes_dir.rglob("*.md"))) if notes_dir.is_dir() else 0
    snapshot_count = (
        len(list((ROOT / "data" / "transcripts" / "snapshots").rglob("*.png")))
        if (ROOT / "data" / "transcripts" / "snapshots").is_dir()
        else 0
    )
    # Code exists vs data on disk — quiz/review cards live in DB (check in coach context).
    input_ready = transcript_count > 0
    notes_generated = note_count > 0
    likely_skipping_assessment = notes_generated and transcript_count > 0
    return {
        "step1_live_captions": (scripts / "run_live_captions_scraper.bat").is_file(),
        "step2_transcript_to_notes": (scripts / "run_transcript_to_notes.bat").is_file(),
        "lecture_notes_route": "/lecture-notes",
        "review_hub_route": "/review",
        "ai_coach_route": "/ai-coach",
        "project_agent_route": "/project-agent",
        "data_transcripts_dir": transcripts_dir.is_dir(),
        "data_notes_dir": notes_dir.is_dir(),
        "transcript_count": transcript_count,
        "note_count_on_disk": note_count,
        "snapshot_png_count": snapshot_count,
        "usage_hint": (
            "You have notes but may be skipping quiz → review. "
            "Open Lecture Notes → Generate quiz → Take quiz → Review Hub."
            if likely_skipping_assessment
            else "Run scraper then transcript_to_notes.bat --latest to start the loop."
            if not notes_generated
            else "Inputs look good — confirm quiz cards in Review Hub (/review)."
        ),
    }


def build_codebase_snapshot(*, force: bool = False) -> dict[str, Any]:
    """Cached overview of routes, CSS, todos, and file counts."""
    global _snapshot_cache, _snapshot_at
    now = time.monotonic()
    if not force and _snapshot_cache and (now - _snapshot_at) < _SNAPSHOT_TTL_SEC:
        return _snapshot_cache

    files = _iter_project_files()
    by_ext: Counter[str] = Counter()
    for f in files:
        by_ext[f.suffix.lower()] += 1

    snapshot: dict[str, Any] = {
        "project_root": str(ROOT),
        "scanned_files": len(files),
        "files_by_extension": dict(by_ext),
        "frontend_routes": _extract_frontend_routes(),
        "api_routes_sample": _extract_api_routes()[:50],
        "api_route_count": len(_extract_api_routes()),
        "css_top_classes": _count_css_classes(files),
        "open_todos": _scan_todos(files),
        "study_pipeline": _pipeline_status(),
        "key_docs": [
            p
            for p in (
                "docs/ROADMAP.md",
                "docs/PROJECT_LAYOUT.md",
                "docs/FILE_MAP.md",
                "AGENTS.md",
            )
            if (ROOT / p).is_file()
        ],
    }
    _snapshot_cache = snapshot
    _snapshot_at = now
    return snapshot


def _score_file(path: Path, keywords: list[str]) -> int:
    rel = _rel(path).lower()
    name = path.name.lower()
    score = 0
    for kw in keywords:
        if kw in name:
            score += 12
        if kw in rel:
            score += 8
    if "component" in keywords and path.suffix in {".tsx", ".jsx"}:
        score += 2
    if "css" in keywords and path.suffix == ".css":
        score += 4
    if "api" in keywords and "router" in name:
        score += 6
    return score


def _read_excerpt(path: Path, keywords: list[str], limit: int = _MAX_EXCERPT) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= limit and not keywords:
        return text
    if keywords:
        lines = text.splitlines()
        hits: list[str] = []
        for i, line in enumerate(lines):
            low = line.lower()
            if any(k in low for k in keywords):
                start = max(0, i - 2)
                end = min(len(lines), i + 8)
                hits.append(f"--- lines {start + 1}-{end} ---")
                hits.extend(lines[start:end])
                hits.append("")
            if sum(len(h) for h in hits) > limit:
                break
        if hits:
            blob = "\n".join(hits)
            return blob[:limit] + ("..." if len(blob) > limit else "")
    return text[:limit] + ("..." if len(text) > limit else "")


def search_codebase(query: str, *, max_files: int = 6) -> list[dict[str, Any]]:
    """Find relevant source files and return path + excerpt for the LLM."""
    keywords = re.findall(r"[a-z0-9_]{3,}", (query or "").lower())[:10]
    if not keywords:
        keywords = ["lecture", "quiz", "coach"]

    files = _iter_project_files()
    scored: list[tuple[int, Path]] = []
    for path in files:
        s = _score_file(path, keywords)
        if s > 0:
            scored.append((s, path))
    scored.sort(key=lambda x: (-x[0], _rel(x[1])))

    results: list[dict[str, Any]] = []
    for _, path in scored[:max_files]:
        results.append(
            {
                "path": _rel(path),
                "extension": path.suffix,
                "size_bytes": path.stat().st_size,
                "excerpt": _read_excerpt(path, keywords),
            }
        )
    return results


def retrieve_codebase_knowledge(query: str = "", *, max_chars: int = 18_000) -> dict[str, Any]:
    """Bundle snapshot + query-matched files for Project Agent chat."""
    snapshot = build_codebase_snapshot()
    files = search_codebase(query, max_files=8)
    payload: dict[str, Any] = {
        "query": (query or "")[:500],
        "snapshot": snapshot,
        "matched_files": files,
        "cursor_pairing_hint": (
            "The student also uses Cursor AI for edits. Give file paths, CSS class names, "
            "and small copy-pasteable tasks they can hand to Cursor."
        ),
    }
    blob = str(payload)
    if len(blob) > max_chars:
        payload["matched_files"] = [
            {**f, "excerpt": f.get("excerpt", "")[:1200]} for f in files[:4]
        ]
        payload["snapshot"] = {
            k: snapshot[k]
            for k in (
                "frontend_routes",
                "api_route_count",
                "css_top_classes",
                "open_todos",
                "study_pipeline",
                "scanned_files",
            )
            if k in snapshot
        }
    return payload


def list_browse_files(prefix: str = "", limit: int = 80) -> list[str]:
    """Flat file list for UI explorer (prefix filter)."""
    files = _iter_project_files()
    rels = sorted(_rel(p) for p in files)
    if prefix:
        low = prefix.lower()
        rels = [r for r in rels if low in r.lower()]
    return rels[:limit]


def read_project_file(relative_path: str, *, max_chars: int = 12_000) -> dict[str, Any]:
    """Read one project file safely (no path traversal)."""
    rel = relative_path.replace("\\", "/").lstrip("/")
    target = (ROOT / rel).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError("Invalid path.")
    if _is_skipped(target.relative_to(ROOT)):
        raise ValueError("Path not allowed.")
    if not target.is_file():
        raise FileNotFoundError(relative_path)
    if target.suffix.lower() not in _TEXT_EXTENSIONS:
        raise ValueError("File type not readable.")
    if target.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("File too large.")
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": rel,
        "size_bytes": target.stat().st_size,
        "content": text[:max_chars] + ("..." if len(text) > max_chars else ""),
        "truncated": len(text) > max_chars,
    }
