"""LAN HTTP hub for Amazfit/CALT Sync — runs inside desktop tracker.

Default bind: 0.0.0.0:8765 (override TRACKER_HUB_PORT / TRACKER_HUB_HOST).
Reuses wearables FastAPI routes + hub remotes (shutdown / lock / gate).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any

log = logging.getLogger("desktop_tracker.hub")

_HUB_VERSION = "3.0.0"
_server: Any = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def hub_port() -> int:
    try:
        return max(1, int(os.environ.get("TRACKER_HUB_PORT", "8765")))
    except ValueError:
        return 8765


def hub_host() -> str:
    return (os.environ.get("TRACKER_HUB_HOST") or "0.0.0.0").strip() or "0.0.0.0"


def _build_app():
    from fastapi import Depends, FastAPI
    from fastapi.responses import JSONResponse
    from sqlalchemy.orm import Session

    from backend.behavior.distraction_gate import compute_distraction_gate
    from backend.core.auth import ensure_solo_owner
    from backend.db.session import get_db
    from backend.wearables.router import require_wearable_key, router as wearables_router

    app = FastAPI(title="CALT Tracker Hub", version=_HUB_VERSION)
    app.include_router(wearables_router)

    @app.get("/health")
    def root_health():
        return {
            "ok": True,
            "service": "calt.tracker_hub",
            "version": _HUB_VERSION,
            "port": hub_port(),
        }

    @app.get("/api/hub/gate")
    def hub_gate(
        db: Session = Depends(get_db),
        _: None = Depends(require_wearable_key),
    ):
        user = ensure_solo_owner(db)
        gate = compute_distraction_gate(db, user.id)
        return {"ok": True, "schema": 1, **gate}

    @app.get("/api/hub/calt-tab-command")
    def hub_calt_tab_command(
        consume: int = 1,
        _: None = Depends(require_wearable_key),
    ):
        """SelfTracker polls this to focus one CALT tab (also exposes last Jarvis line)."""
        from backend.behavior import calt_tab_command as ctc

        cmd = ctc.consume_command() if consume else ctc.peek_command()
        jarvis = ctc.last_jarvis_line_payload()
        return {"ok": True, "command": cmd, "jarvis": jarvis}

    @app.post("/api/hub/calt-tab-command")
    def hub_calt_tab_command_post(
        body: dict | None = None,
        _: None = Depends(require_wearable_key),
    ):
        from backend.behavior import calt_tab_command as ctc

        path = str((body or {}).get("path") or "/").strip() or "/"
        return ctc.request_focus(path, force=bool((body or {}).get("force")))


    @app.post("/api/hub/shutdown")
    def hub_shutdown(_: None = Depends(require_wearable_key)):
        if os.name != "nt":
            return JSONResponse({"ok": False, "error": "Windows only"}, status_code=400)
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", "30", "/c", "CALT Sync: shutting down in 30s"],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
        log.info("Shutdown scheduled (30s) via tracker hub")
        return {
            "ok": True,
            "seconds": 30,
            "cancel_path": "/api/hub/shutdown/cancel",
            "hint": "Cancel from watch More, or run: shutdown /a",
        }

    @app.post("/api/hub/shutdown/cancel")
    def hub_shutdown_cancel(_: None = Depends(require_wearable_key)):
        if os.name != "nt":
            return JSONResponse({"ok": False, "error": "Windows only"}, status_code=400)
        try:
            r = subprocess.run(
                ["shutdown", "/a"],
                check=False,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
        log.info("Shutdown cancel exit=%s", r.returncode)
        return {
            "ok": True,
            "cancelled": r.returncode == 0,
            "detail": (r.stderr or r.stdout or "").strip()[:200],
        }

    @app.post("/api/hub/lock")
    def hub_lock(_: None = Depends(require_wearable_key)):
        if os.name != "nt":
            return JSONResponse({"ok": False, "error": "Windows only"}, status_code=400)
        try:
            subprocess.run(
                ["rundll32.exe", "user32.dll,LockWorkStation"],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
        log.info("Workstation lock requested via tracker hub")
        return {"ok": True}

    @app.get("/api/hub/bible-verse")
    def hub_bible_verse(
        db: Session = Depends(get_db),
        _: None = Depends(require_wearable_key),
    ):
        """Rotating verse from chapters completed today (for Amazfit / CALT Sync)."""
        from backend.bible import store as bible_store
        from backend.bible import structured as bible_text

        user = ensure_solo_owner(db)
        keys = bible_store.chapters_completed_today(user.id)
        # Also include currently open chapter if set
        summary = bible_store.summary(user.id)
        cur_book = str(summary.get("last_book") or "")
        cur_ch = int(summary.get("last_chapter") or 0)
        if cur_book and cur_ch > 0:
            cur_key = bible_text.chapter_key(cur_book, cur_ch)
            if cur_key not in keys:
                keys = [*keys, cur_key]
        pool = bible_text.verses_for_chapter_keys(keys, version="web", limit=400)
        if not pool:
            return {
                "ok": True,
                "schema": 1,
                "ref": "",
                "text": "Read one chapter to feed the watch.",
                "book": "",
                "chapter": 0,
                "verse": 0,
                "rotation_index": 0,
                "source_chapters": [],
                "fallback": True,
            }
        # Rotate every ~10 minutes by local minute bucket
        import time as _time

        idx = int(_time.time() // 600) % len(pool)
        v = pool[idx]
        return {
            "ok": True,
            "schema": 1,
            "ref": v["ref"],
            "text": v["text"],
            "book": v["book"],
            "chapter": v["chapter"],
            "verse": v["verse"],
            "rotation_index": idx,
            "source_chapters": keys,
            "fallback": False,
        }

    # --- CALT Voice notes (chunked Opus upload from the watch) ---------------

    def _voice_note_error(exc: Exception, status: int):
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=status)

    @app.post("/api/hub/voice-note/begin")
    def hub_voice_note_begin(
        body: dict | None = None,
        _: None = Depends(require_wearable_key),
    ):
        from backend.behavior import voice_notes

        b = body or {}
        try:
            return voice_notes.begin_upload(
                name=b.get("name"),
                size=b.get("size"),
                chunk_size=b.get("chunk_size"),
                total_chunks=b.get("total_chunks"),
                sha=b.get("sha"),
            )
        except (ValueError, TypeError, KeyError) as e:
            return _voice_note_error(e, 400)
        except OSError as e:
            return _voice_note_error(e, 500)

    @app.post("/api/hub/voice-note/chunk")
    def hub_voice_note_chunk(
        body: dict | None = None,
        _: None = Depends(require_wearable_key),
    ):
        from backend.behavior import voice_notes

        b = body or {}
        try:
            return voice_notes.accept_chunk(
                upload_id=b.get("upload_id"),
                index=b.get("index"),
                data_b64=b.get("data"),
                checksum=b.get("checksum"),
            )
        except LookupError as e:
            return _voice_note_error(e, 404)
        except (ValueError, TypeError, KeyError) as e:
            return _voice_note_error(e, 400)
        except OSError as e:
            return _voice_note_error(e, 500)

    @app.post("/api/hub/voice-note/finish")
    def hub_voice_note_finish(
        body: dict | None = None,
        _: None = Depends(require_wearable_key),
    ):
        from backend.behavior import voice_notes

        try:
            return voice_notes.finish_upload(upload_id=(body or {}).get("upload_id"))
        except LookupError as e:
            return _voice_note_error(e, 404)
        except OSError as e:
            return _voice_note_error(e, 500)

    @app.get("/api/hub/voice-note/status")
    def hub_voice_note_status(
        upload_id: str,
        _: None = Depends(require_wearable_key),
    ):
        from backend.behavior import voice_notes

        return voice_notes.upload_status(upload_id=upload_id)

    @app.get("/api/hub/voice-note/list")
    def hub_voice_note_list(_: None = Depends(require_wearable_key)):
        from backend.behavior import voice_notes

        return {"ok": True, "notes": voice_notes.list_notes()}

    return app


def start_tracker_hub() -> bool:
    """Start uvicorn hub in a daemon thread. Idempotent."""
    global _server, _thread
    with _lock:
        if _thread and _thread.is_alive():
            return True
        if os.environ.get("TRACKER_HUB_DISABLE", "").strip().lower() in ("1", "true", "yes"):
            log.info("Tracker hub disabled (TRACKER_HUB_DISABLE)")
            return False

        host = hub_host()
        port = hub_port()

        try:
            import uvicorn
        except ImportError:
            log.warning("uvicorn missing — tracker hub not started")
            return False

        try:
            app = _build_app()
        except Exception as e:  # noqa: BLE001
            log.warning("Tracker hub build failed: %s", e)
            return False

        try:
            # log_config=None: tracker's logging is already configured; uvicorn's
            # default dictConfig fails with "Unable to configure formatter 'default'".
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="warning",
                access_log=False,
                log_config=None,
                workers=1,
                reload=False,
                lifespan="off",
            )
            server = uvicorn.Server(config)
        except Exception as e:  # noqa: BLE001
            log.warning("Tracker hub uvicorn config failed: %s", e)
            return False

        _server = server

        def run() -> None:
            try:
                server.run()
            except Exception as exc:  # noqa: BLE001
                log.warning("Tracker hub stopped: %s", exc)

        _thread = threading.Thread(target=run, name="tracker-hub", daemon=True)
        _thread.start()
        log.info("Tracker LAN hub listening on http://%s:%s (CALT Sync Base URL)", host, port)
        return True


def stop_tracker_hub() -> None:
    global _server, _thread
    with _lock:
        srv = _server
        _server = None
        if srv is not None:
            try:
                srv.should_exit = True
            except Exception:  # noqa: BLE001
                pass
        _thread = None
