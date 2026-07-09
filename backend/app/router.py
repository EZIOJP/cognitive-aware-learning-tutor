"""Mobile app distribution — CALT Android APK served from data/downloads/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.paths import DOWNLOADS_DIR

router = APIRouter(prefix="/api/app", tags=["app"])

APK_FILENAME = "calt-android.apk"
MANIFEST_FILENAME = "calt-android.manifest.json"


def _apk_path() -> Path:
    return DOWNLOADS_DIR / APK_FILENAME


def _manifest_path() -> Path:
    return DOWNLOADS_DIR / MANIFEST_FILENAME


def _read_manifest() -> dict:
    path = _manifest_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _apk_metadata(request: Request) -> dict:
    path = _apk_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CALT Android build not available on this server")

    manifest = _read_manifest()
    stat = path.stat()
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    base = str(request.base_url).rstrip("/")

    return {
        "app_id": "calt-android",
        "package": manifest.get("package", "com.calt.timetable"),
        "version_name": manifest.get("version_name", "unknown"),
        "version_code": manifest.get("version_code", 0),
        "release_notes": manifest.get("release_notes", ""),
        "size_bytes": stat.st_size,
        "updated_at": manifest.get("updated_at", updated_at),
        "download_url": f"{base}/api/app/calt-android/download",
        "filename": APK_FILENAME,
    }


@router.get("/calt-android/latest")
def calt_android_latest(request: Request):
    """Metadata for the newest CALT Timetable APK on this server."""
    return _apk_metadata(request)


@router.get("/calt-android/download")
def calt_android_download():
    """Download the CALT Timetable APK (install on Android from phone browser)."""
    path = _apk_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="APK not found — run scripts/publish_calt_apk.bat")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=APK_FILENAME,
    )
