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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker.voice_notes")

NOTES_DIR = ROOT / "data" / "voice_notes"
PARTIAL_DIR = NOTES_DIR / ".partial"
SYNC_STATE_PATH = ROOT / "data" / "behavior" / "voice_last_sync.json"

MAX_NOTE_BYTES = 32 * 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}\.opus$")

_lock = threading.RLock()


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


def _final_is_valid(final: Path, *, size: int, sha: str) -> bool:
    """True only when the published file matches declared size and whole-file hash."""
    try:
        if not final.is_file() or final.stat().st_size != size:
            return False
        return fnv1a32(final.read_bytes()) == str(sha)
    except OSError:
        return False


def _remove_final_if_invalid(final: Path, *, size: int, sha: str) -> None:
    """Drop a stale or corrupt published clip so a fresh upload can replace it."""
    if not final.exists():
        return
    if _final_is_valid(final, size=size, sha=sha):
        return
    try:
        final.unlink()
        log.warning("Removed invalid voice note on disk: %s", final.name)
    except OSError as exc:
        log.debug("voice note unlink failed: %s", exc)


def _finish_upload_locked(manifest: dict[str, Any], upload_id: str) -> dict[str, Any]:
    """Verify the reassembled file and publish it atomically (lock must be held)."""
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
        _discard(upload_id)
        return {"ok": False, "error": "file_checksum_mismatch", "restart": True}

    gain = _normalize_gain(manifest.get("gain"))
    from backend.behavior.voice_opus_gain import amplify_zepp_opus

    published = amplify_zepp_opus(blob, gain)

    final = NOTES_DIR / str(manifest["name"])
    tmp = final.with_suffix(f"{final.suffix}.tmp")
    try:
        tmp.write_bytes(published)
        os.replace(tmp, final)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    try:
        part.unlink()
    except OSError:
        pass
    try:
        _manifest_path(upload_id).unlink()
    except OSError:
        pass

    log.info(
        "Voice note stored: %s (%d bytes, gain=%.2f)",
        final.name,
        len(published),
        gain,
    )
    _write_sync_state(name=final.name, size=len(published))
    return {
        "ok": True,
        "stored": True,
        "name": final.name,
        "size": len(published),
        "gain": gain,
        "path": str(final),
    }


def _normalize_gain(raw: Any) -> float:
    try:
        g = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return max(0.25, min(8.0, g))


def begin_upload(
    *,
    name: str,
    size: int,
    chunk_size: int,
    total_chunks: int,
    sha: str,
    gain: float | None = None,
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
    record_gain = _normalize_gain(gain if gain is not None else 1.0)

    with _lock:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

        final = NOTES_DIR / safe
        _remove_final_if_invalid(final, size=size, sha=str(sha))
        if _final_is_valid(final, size=size, sha=str(sha)):
            # Already published and verified; let the watch delete its copy.
            _write_sync_state(name=safe, size=size)
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
                "gain": record_gain,
                "received": [],
            }
            _write_manifest(upload_id, manifest)
        else:
            manifest["gain"] = record_gain
            _write_manifest(upload_id, manifest)

        received = sorted(int(i) for i in manifest.get("received") or [])
        complete = len(received) == total_chunks
        if complete:
            # All chunks are present but VN_FINISH may have failed mid-flight.
            finished = _finish_upload_locked(manifest, upload_id)
            if finished.get("ok") and finished.get("stored"):
                finished.setdefault("upload_id", upload_id)
                finished.setdefault("received", received)
                finished.setdefault("complete", True)
                return finished
            finished.setdefault("upload_id", upload_id)
            finished.setdefault("received", received)
            finished.setdefault("complete", True)
            return finished

        return {
            "ok": True,
            "upload_id": upload_id,
            "received": received,
            "complete": complete,
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
            fh.flush()
            os.fsync(fh.fileno())

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
        return _finish_upload_locked(manifest, upload_id)


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


def list_pending_uploads() -> list[dict[str, Any]]:
    """In-progress chunked uploads waiting for watch chunks."""
    out: list[dict[str, Any]] = []
    try:
        if not PARTIAL_DIR.is_dir():
            return out
        for path in sorted(PARTIAL_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            received = sorted(int(i) for i in data.get("received") or [])
            total = int(data.get("total_chunks") or 0)
            out.append(
                {
                    "upload_id": data.get("upload_id") or path.stem,
                    "name": data.get("name"),
                    "received_count": len(received),
                    "total_chunks": total,
                    "complete": total > 0 and len(received) == total,
                }
            )
    except OSError:
        pass
    return out


def _write_sync_state(*, name: str, size: int) -> None:
    payload = {
        "last_upload_at": datetime.now(timezone.utc).isoformat(),
        "last_name": str(name),
        "last_size": int(size),
    }
    try:
        SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log.debug("voice sync state write failed: %s", exc)


def read_sync_state() -> dict[str, Any]:
    try:
        if SYNC_STATE_PATH.is_file():
            data = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


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
