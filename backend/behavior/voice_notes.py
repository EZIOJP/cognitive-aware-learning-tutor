"""Chunked voice-note upload from the CALT Voice watch app.

BLE messaging cannot carry a whole Opus clip in one payload, so the watch reads
the file in fixed-size pieces and relays them through the phone side service.

The protocol is built for reliability rather than speed, because a half-written
recording is worse than a slow one:

* every chunk carries its own checksum and is rejected if it does not match,
* chunks land at a fixed offset in a preallocated ``.part`` file, so a replayed
  chunk rewrites the same bytes instead of appending a duplicate,
* the reassembled file must match both the declared size and a whole-file
  checksum before it is published,
* publishing is an ``os.replace`` onto the final path, so a reader never sees a
  partially written ``.opus``.

The watch deletes its local copy only after ``finish_upload`` reports the file
as stored, so an interrupted transfer costs bandwidth, never data.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("desktop_tracker.voice_notes")

NOTES_DIR = Path("data/voice_notes")
PARTIAL_DIR = NOTES_DIR / ".partial"

MAX_NOTE_BYTES = 32 * 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}\.opus$")

_lock = threading.Lock()


def fnv1a32(data: bytes) -> str:
    """FNV-1a, matching the watch's JS implementation byte for byte.

    Kept unpadded because JS ``(h >>> 0).toString(16)`` does not pad, and the
    two sides compare these strings directly.
    """
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return f"h{h:x}"


def _safe_name(name: str) -> str:
    """Whitelist the filename outright.

    Refuses rather than sanitizes: the watch only ever sends ``voice_*.opus``,
    so anything with a separator in it means something upstream is wrong, and
    quietly rewriting it would hide that. The character whitelist also makes
    path traversal unrepresentable.
    """
    clean = str(name or "").strip()
    if not _NAME_RE.match(clean):
        raise ValueError("bad_name")
    return clean


def _upload_id(name: str, size: int, sha: str) -> str:
    return fnv1a32(f"{name}|{size}|{sha}".encode())


def _manifest_path(upload_id: str) -> Path:
    return PARTIAL_DIR / f"{upload_id}.json"


def _part_path(upload_id: str) -> Path:
    return PARTIAL_DIR / f"{upload_id}.part"


def _read_manifest(upload_id: str) -> dict[str, Any] | None:
    path = _manifest_path(upload_id)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_manifest(upload_id: str, manifest: dict[str, Any]) -> None:
    path = _manifest_path(upload_id)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    os.replace(tmp, path)


def _discard(upload_id: str) -> None:
    for path in (_part_path(upload_id), _manifest_path(upload_id)):
        try:
            path.unlink()
        except OSError:
            pass


def begin_upload(
    *,
    name: str,
    size: int,
    chunk_size: int,
    total_chunks: int,
    sha: str,
) -> dict[str, Any]:
    """Open (or resume) an upload and report which chunks are already held."""
    safe = _safe_name(name)
    size = int(size)
    chunk_size = int(chunk_size)
    total_chunks = int(total_chunks)

    if not 0 < size <= MAX_NOTE_BYTES:
        raise ValueError("bad_size")
    if not 0 < chunk_size <= MAX_CHUNK_BYTES:
        raise ValueError("bad_chunk_size")
    expected_chunks = (size + chunk_size - 1) // chunk_size
    if total_chunks != expected_chunks:
        raise ValueError("chunk_count_mismatch")

    upload_id = _upload_id(safe, size, str(sha))

    with _lock:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

        final = NOTES_DIR / safe
        if final.exists() and final.stat().st_size == size:
            # Already published by an earlier run; let the watch delete its copy.
            return {
                "ok": True,
                "upload_id": upload_id,
                "received": [],
                "complete": True,
                "stored": True,
                "path": str(final),
            }

        manifest = _read_manifest(upload_id)
        part = _part_path(upload_id)
        if manifest is None or not part.exists():
            _discard(upload_id)
            with open(part, "wb") as fh:
                fh.truncate(size)
            manifest = {
                "upload_id": upload_id,
                "name": safe,
                "size": size,
                "chunk_size": chunk_size,
                "total_chunks": total_chunks,
                "sha": str(sha),
                "received": [],
            }
            _write_manifest(upload_id, manifest)

        received = sorted(int(i) for i in manifest.get("received") or [])
        return {
            "ok": True,
            "upload_id": upload_id,
            "received": received,
            "complete": len(received) == total_chunks,
            "stored": False,
        }


def accept_chunk(
    *,
    upload_id: str,
    index: int,
    data_b64: str,
    checksum: str,
) -> dict[str, Any]:
    """Verify one chunk and write it at its fixed offset."""
    index = int(index)

    with _lock:
        manifest = _read_manifest(upload_id)
        if manifest is None:
            raise LookupError("unknown_upload")

        size = int(manifest["size"])
        chunk_size = int(manifest["chunk_size"])
        total_chunks = int(manifest["total_chunks"])
        if not 0 <= index < total_chunks:
            raise ValueError("index_out_of_range")

        try:
            raw = base64.b64decode(str(data_b64), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("bad_base64") from exc

        offset = index * chunk_size
        expected_len = min(chunk_size, size - offset)
        if len(raw) != expected_len:
            raise ValueError("bad_chunk_length")

        actual = fnv1a32(raw)
        if str(checksum) != actual:
            # Do not record it: the watch will resend this index.
            raise ValueError("checksum_mismatch")

        part = _part_path(upload_id)
        if not part.exists():
            raise LookupError("part_missing")
        with open(part, "r+b") as fh:
            fh.seek(offset)
            fh.write(raw)

        received = set(int(i) for i in manifest.get("received") or [])
        received.add(index)
        manifest["received"] = sorted(received)
        _write_manifest(upload_id, manifest)

        return {
            "ok": True,
            "upload_id": upload_id,
            "index": index,
            "received_count": len(received),
            "total_chunks": total_chunks,
            "complete": len(received) == total_chunks,
        }


def finish_upload(*, upload_id: str) -> dict[str, Any]:
    """Verify the reassembled file and publish it atomically."""
    with _lock:
        manifest = _read_manifest(upload_id)
        if manifest is None:
            raise LookupError("unknown_upload")

        size = int(manifest["size"])
        total_chunks = int(manifest["total_chunks"])
        received = set(int(i) for i in manifest.get("received") or [])
        missing = sorted(set(range(total_chunks)) - received)
        if missing:
            return {
                "ok": False,
                "error": "incomplete",
                "missing": missing[:64],
                "missing_count": len(missing),
            }

        part = _part_path(upload_id)
        try:
            blob = part.read_bytes()
        except OSError as exc:
            raise LookupError("part_missing") from exc

        if len(blob) != size:
            _discard(upload_id)
            return {"ok": False, "error": "size_mismatch", "restart": True}

        actual = fnv1a32(blob)
        if actual != str(manifest.get("sha")):
            # Chunks each passed, but the whole does not. Force a clean restart
            # rather than publishing a file that will not decode.
            _discard(upload_id)
            return {"ok": False, "error": "file_checksum_mismatch", "restart": True}

        final = NOTES_DIR / str(manifest["name"])
        os.replace(part, final)
        try:
            _manifest_path(upload_id).unlink()
        except OSError:
            pass

        log.info("Voice note stored: %s (%d bytes)", final.name, size)
        return {
            "ok": True,
            "stored": True,
            "name": final.name,
            "size": size,
            "path": str(final),
        }


def upload_status(*, upload_id: str) -> dict[str, Any]:
    with _lock:
        manifest = _read_manifest(upload_id)
        if manifest is None:
            return {"ok": False, "error": "unknown_upload"}
        received = sorted(int(i) for i in manifest.get("received") or [])
        total = int(manifest["total_chunks"])
        return {
            "ok": True,
            "upload_id": upload_id,
            "name": manifest.get("name"),
            "received": received,
            "received_count": len(received),
            "total_chunks": total,
            "complete": len(received) == total,
        }


def list_notes() -> list[dict[str, Any]]:
    try:
        entries = sorted(NOTES_DIR.glob("*.opus"))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for path in entries:
        try:
            st = path.stat()
        except OSError:
            continue
        out.append({"name": path.name, "size": st.st_size, "mtime": st.st_mtime})
    out.sort(key=lambda row: row["mtime"], reverse=True)
    return out


def resolve_note_path(name: str) -> Path:
    """Return the on-disk path for a stored clip (web download / open)."""
    safe = _safe_name(name)
    path = NOTES_DIR / safe
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path
