"""Automated wikilink injection for markdown lecture notes.

Algorithm:
1. Scan all .md files in the output folder and build an index:
       heading_text → source_file_name (stem)
2. In the newly generated note, locate every occurrence of an indexed
   heading title in plain text — not inside a code fence, URL, or
   existing [[...]] link.
3. Wrap the first occurrence per heading per file with [[Heading Title]].
4. For every linked target file, append or update a ## Backlinks section.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BACKLINKS_HEADER = "## Backlinks"
BACKLINKS_SEPARATOR = "\n\n---\n\n" + BACKLINKS_HEADER + "\n"
H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
H3_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
URL_RE = re.compile(r"https?://\S+")


# ---------------------------------------------------------------------------
# Code-fence state machine
# ---------------------------------------------------------------------------

def _code_regions(text: str) -> list[tuple[int, int]]:
    """Return list of (start, end) char ranges that are inside a code fence."""
    regions: list[tuple[int, int]] = []
    lines = text.split("\n")
    pos = 0
    in_fence = False
    fence_start = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_start = pos
            else:
                in_fence = False
                regions.append((fence_start, pos + len(line)))
        pos += len(line) + 1  # +1 for '\n'
    if in_fence:
        regions.append((fence_start, len(text)))
    return regions


def _in_code(pos: int, regions: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in regions)


# ---------------------------------------------------------------------------
# Heading index
# ---------------------------------------------------------------------------

def build_heading_index(folder: Path) -> dict[str, str]:
    """Return {heading_text: file_stem} for all ## and ### headings in .md files."""
    index: dict[str, str] = {}
    for md_file in sorted(folder.rglob("*.md")):
        stem = md_file.stem
        content = _safe_read(md_file)
        for m in H2_RE.finditer(content):
            heading = m.group(1).strip()
            if heading and heading not in index:
                index[heading] = stem
        for m in H3_RE.finditer(content):
            heading = m.group(1).strip()
            if heading and heading not in index:
                index[heading] = stem
    return index


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Wikilink injection into a single note
# ---------------------------------------------------------------------------

def _inject_wikilinks_in_text(
    content: str,
    heading_index: dict[str, str],
    own_stem: str,
) -> tuple[str, set[str]]:
    """Inject [[...]] wikilinks into content.

    Returns (modified_content, set_of_link_targets_referenced).
    """
    code_zones = _code_regions(content)
    linked_targets: set[str] = set()

    # Sort headings longest-first to avoid partial matches
    sorted_headings = sorted(heading_index.keys(), key=len, reverse=True)

    for heading in sorted_headings:
        target_stem = heading_index[heading]
        if target_stem == own_stem:
            continue  # Don't self-link

        escaped = re.escape(heading)
        # Match heading text NOT already inside [[...]] and not in URLs
        # Negative lookbehind for [ and negative lookahead for ]]
        pattern = re.compile(rf"(?<!\[)(?<!\[\[){escaped}(?!\]\])(?!\])")

        new_parts: list[str] = []
        last_end = 0
        already_linked = False

        for m in pattern.finditer(content):
            start, end = m.start(), m.end()
            if _in_code(start, code_zones):
                continue
            # Only link first occurrence per heading to avoid clutter
            if already_linked:
                break
            new_parts.append(content[last_end:start])
            new_parts.append(f"[[{heading}]]")
            last_end = end
            already_linked = True

        if new_parts:
            new_parts.append(content[last_end:])
            content = "".join(new_parts)
            linked_targets.add(target_stem)
            # Recalculate code zones after modification
            code_zones = _code_regions(content)

    return content, linked_targets


# ---------------------------------------------------------------------------
# Backlinks management
# ---------------------------------------------------------------------------

def _strip_backlinks_section(content: str) -> str:
    """Remove existing ## Backlinks section (everything from separator or header to EOF)."""
    # Try separator form first
    idx = content.find("\n\n---\n\n" + BACKLINKS_HEADER)
    if idx != -1:
        return content[:idx].rstrip()
    # Try plain header form
    idx = content.find("\n" + BACKLINKS_HEADER)
    if idx != -1:
        return content[:idx].rstrip()
    return content


def _add_backlink(
    target_path: Path,
    source_name: str,
    heading_text: str,
) -> None:
    """Append or update the backlinks section of a target markdown file."""
    content = _safe_read(target_path)
    body = _strip_backlinks_section(content)

    # Rebuild backlinks by re-parsing existing + adding new
    backlink_entry = f"- [[{source_name}]] → {heading_text}"

    # Extract existing backlinks if any
    existing_backlinks: list[str] = []
    if BACKLINKS_HEADER in content:
        bl_section = content[content.find(BACKLINKS_HEADER) + len(BACKLINKS_HEADER):]
        for line in bl_section.splitlines():
            line = line.strip()
            if line.startswith("- ") and line not in existing_backlinks:
                existing_backlinks.append(line)

    if backlink_entry not in existing_backlinks:
        existing_backlinks.append(backlink_entry)

    bl_block = BACKLINKS_SEPARATOR + "\n".join(existing_backlinks)
    new_content = body + bl_block + "\n"
    try:
        target_path.write_text(new_content, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_wikilinks(
    note_path: Path,
    *,
    folder: Path | None = None,
) -> Path:
    """Inject wikilinks into note_path and update backlinks in linked notes.

    Args:
        note_path: The newly generated markdown note.
        folder: Root folder to scan for all .md files (defaults to note_path.parent).

    Returns:
        The note_path (unchanged).
    """
    if not note_path.is_file():
        return note_path

    scan_root = folder or note_path.parent
    heading_index = build_heading_index(scan_root)
    if not heading_index:
        return note_path

    own_stem = note_path.stem
    content = _safe_read(note_path)

    # Strip any old backlinks from this file before re-injecting
    content = _strip_backlinks_section(content)

    modified, linked_targets = _inject_wikilinks_in_text(content, heading_index, own_stem)

    try:
        note_path.write_text(modified, encoding="utf-8")
    except OSError:
        return note_path

    # Update backlinks in each target file
    for target_stem in linked_targets:
        # Find the target file
        for md_file in scan_root.rglob(f"{target_stem}.md"):
            heading_in_source = next(
                (h for h, s in heading_index.items() if s == target_stem),
                target_stem,
            )
            _add_backlink(md_file, own_stem, heading_in_source)
            break

    return note_path
