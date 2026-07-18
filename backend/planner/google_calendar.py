"""Push CALT planner blocks → Google Calendar (Amazfit picks up via phone calendar)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.config import get_settings
from backend.paths import ROOT

log = logging.getLogger(__name__)

_TOKEN_PATH = ROOT / "data" / "google_calendar_oauth.json"
_CLIENT_PATH = ROOT / "data" / "google_oauth_client.json"
_SCOPES = "https://www.googleapis.com/auth/calendar.events"
_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CAL_API = "https://www.googleapis.com/calendar/v3"
_EXT_KEY = "caltBlockId"


def _load_token() -> dict[str, Any]:
    try:
        if _TOKEN_PATH.is_file():
            return json.loads(_TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_token(data: dict[str, Any]) -> None:
    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cur = _load_token()
    cur.update(data)
    cur["updated_at"] = datetime.now(timezone.utc).isoformat()
    _TOKEN_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")


def _load_client_file() -> dict[str, Any]:
    try:
        if _CLIENT_PATH.is_file():
            return json.loads(_CLIENT_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def oauth_client_credentials() -> tuple[str, str]:
    """Client id/secret from .env, else local data/google_oauth_client.json (UI paste)."""
    s = get_settings()
    cid = (getattr(s, "google_oauth_client_id", None) or "").strip()
    secret = (getattr(s, "google_oauth_client_secret", None) or "").strip()
    if cid and secret:
        return cid, secret
    file_creds = _load_client_file()
    cid = (file_creds.get("client_id") or "").strip()
    secret = (file_creds.get("client_secret") or "").strip()
    return cid, secret


def save_oauth_client(client_id: str, client_secret: str) -> dict[str, Any]:
    cid = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not cid or not secret:
        raise ValueError("Both client_id and client_secret are required")
    if len(cid) < 20 or len(secret) < 10:
        raise ValueError("Client ID / secret look too short — paste the full values from Google Cloud")
    _CLIENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": cid,
        "client_secret": secret,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ui",
    }
    _CLIENT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return google_calendar_configured()


def clear_oauth_client() -> None:
    try:
        if _CLIENT_PATH.is_file():
            _CLIENT_PATH.unlink()
    except Exception:
        pass


def google_calendar_configured() -> dict[str, Any]:
    s = get_settings()
    cid, secret = oauth_client_credentials()
    tok = _load_token()
    has_refresh = bool(
        (tok.get("refresh_token") or getattr(s, "google_calendar_refresh_token", "") or "").strip()
    )
    return {
        "client_configured": bool(cid and secret),
        "connected": has_refresh,
        "calendar_id": (getattr(s, "google_calendar_id", None) or "primary").strip() or "primary",
        "has_access_token": bool(tok.get("access_token")),
        "redirect_uri": auth_redirect_uri(),
        "setup_url": "https://console.cloud.google.com/apis/credentials",
    }


def auth_redirect_uri() -> str:
    s = get_settings()
    custom = (getattr(s, "google_oauth_redirect_uri", None) or "").strip()
    if custom:
        return custom
    return "http://127.0.0.1:8000/api/planner/google-calendar/callback"


def build_auth_url(state: str = "calt") -> str:
    cid, _secret = oauth_client_credentials()
    if not cid:
        raise ValueError("Paste Google OAuth Client ID first (or set GOOGLE_OAUTH_CLIENT_ID)")
    q = urlencode(
        {
            "client_id": cid,
            "redirect_uri": auth_redirect_uri(),
            "response_type": "code",
            "scope": _SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{_AUTH_URI}?{q}"


def exchange_code(code: str) -> dict[str, Any]:
    cid, secret = oauth_client_credentials()
    if not cid or not secret:
        raise ValueError("Google OAuth client id/secret missing")
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            _TOKEN_URI,
            data={
                "code": code,
                "client_id": cid,
                "client_secret": secret,
                "redirect_uri": auth_redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        r.raise_for_status()
        data = r.json()
    _save_token(
        {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token") or _load_token().get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "token_type": data.get("token_type"),
            "scope": data.get("scope"),
        }
    )
    return {"ok": True, "connected": True}


def _refresh_access_token() -> str:
    s = get_settings()
    tok = _load_token()
    refresh = (
        (tok.get("refresh_token") or "").strip()
        or (getattr(s, "google_calendar_refresh_token", None) or "").strip()
    )
    if not refresh:
        raise ValueError("Not connected — open Google Calendar connect from Productivity")
    cid, secret = oauth_client_credentials()
    if not cid or not secret:
        raise ValueError("Google OAuth client id/secret missing")
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            _TOKEN_URI,
            data={
                "client_id": cid,
                "client_secret": secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        data = r.json()
    access = data.get("access_token")
    if not access:
        raise ValueError("No access_token from Google")
    patch = {"access_token": access, "expires_in": data.get("expires_in")}
    if data.get("refresh_token"):
        patch["refresh_token"] = data["refresh_token"]
    _save_token(patch)
    return access


def _access_token() -> str:
    tok = _load_token()
    if tok.get("access_token"):
        return str(tok["access_token"])
    return _refresh_access_token()


def _ics_escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fmt_ics_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def blocks_to_ics(blocks: list[dict[str, Any]], *, calendar_name: str = "CALT Study") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CALT//Planner//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_escape(calendar_name)}",
    ]
    now = _fmt_ics_dt(datetime.now(timezone.utc))
    for b in blocks:
        bid = b.get("id")
        title = str(b.get("title") or "Study")
        start = b.get("start_at")
        end = b.get("end_at")
        if not start or not end:
            continue
        try:
            if isinstance(start, str):
                sdt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            else:
                sdt = start
            if isinstance(end, str):
                edt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            else:
                edt = end
        except Exception:
            continue
        uid = f"calt-block-{bid}@local"
        cat = str(b.get("category") or "study")
        status = str(b.get("status") or "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART:{_fmt_ics_dt(sdt)}",
                f"DTEND:{_fmt_ics_dt(edt)}",
                f"SUMMARY:{_ics_escape(title)}",
                f"DESCRIPTION:{_ics_escape(f'CALT · {cat} · {status}')}",
                f"CATEGORIES:{_ics_escape(cat)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _event_body(block: dict[str, Any]) -> dict[str, Any]:
    start = block["start_at"]
    end = block["end_at"]
    if isinstance(start, datetime):
        start = start.isoformat()
    if isinstance(end, datetime):
        end = end.isoformat()
    bid = str(block.get("id"))
    return {
        "summary": str(block.get("title") or "Study"),
        "description": f"CALT planner block #{bid}\nCategory: {block.get('category') or 'study'}",
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
        "extendedProperties": {"private": {_EXT_KEY: bid}},
    }


def sync_blocks_to_google(
    blocks: list[dict[str, Any]],
    *,
    calendar_id: str | None = None,
) -> dict[str, Any]:
    """Create or update Google Calendar events for planner blocks."""
    s = get_settings()
    cal_id = (calendar_id or getattr(s, "google_calendar_id", None) or "primary").strip() or "primary"
    created = updated = skipped = 0
    errors: list[str] = []

    try:
        token = _access_token()
    except Exception as e:
        # one refresh retry
        try:
            token = _refresh_access_token()
        except Exception as e2:
            return {
                "ok": False,
                "error": str(e2 or e),
                "created": 0,
                "updated": 0,
                "hint": "Connect Google in Productivity → Calendar, or set GOOGLE_OAUTH_* in .env",
            }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Fail fast with a clear message if Calendar API / scope is missing.
    with httpx.Client(timeout=45.0) as client:
        probe = client.get(f"{_CAL_API}/calendars/{cal_id}/events?maxResults=1", headers=headers)
        if probe.status_code == 401:
            token = _refresh_access_token()
            headers["Authorization"] = f"Bearer {token}"
            probe = client.get(f"{_CAL_API}/calendars/{cal_id}/events?maxResults=1", headers=headers)
        if probe.status_code == 403:
            return {
                "ok": False,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "error": "Google Calendar API returned 403 Forbidden",
                "hint": (
                    "Enable Google Calendar API for your Cloud project: "
                    "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com "
                    "Then in CALT click Connect Google again (reconnect) and Push."
                ),
            }
        if probe.status_code >= 400:
            return {
                "ok": False,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "error": f"Calendar access failed ({probe.status_code})",
                "hint": probe.text[:240] or "Reconnect Google and ensure Calendar API is enabled.",
            }

        for b in blocks:
            bid = b.get("id")
            if bid is None:
                skipped += 1
                continue
            if str(b.get("status") or "") in ("cancelled", "rolled"):
                skipped += 1
                continue
            try:
                # Find existing by private extended property
                q = urlencode({"privateExtendedProperty": f"{_EXT_KEY}={bid}", "maxResults": 5})
                fr = client.get(f"{_CAL_API}/calendars/{cal_id}/events?{q}", headers=headers)
                if fr.status_code == 401:
                    token = _refresh_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    fr = client.get(f"{_CAL_API}/calendars/{cal_id}/events?{q}", headers=headers)
                fr.raise_for_status()
                items = (fr.json() or {}).get("items") or []
                body = _event_body(b)
                # Prefer local timezone strings without forcing UTC if already offset
                for key in ("start", "end"):
                    raw = b.get("start_at") if key == "start" else b.get("end_at")
                    if isinstance(raw, str) and ("+" in raw[10:] or raw.endswith("Z")):
                        body[key] = {"dateTime": raw}
                if items:
                    eid = items[0]["id"]
                    ur = client.patch(
                        f"{_CAL_API}/calendars/{cal_id}/events/{eid}",
                        headers=headers,
                        json=body,
                    )
                    ur.raise_for_status()
                    updated += 1
                else:
                    cr = client.post(
                        f"{_CAL_API}/calendars/{cal_id}/events",
                        headers=headers,
                        json=body,
                    )
                    cr.raise_for_status()
                    created += 1
            except Exception as e:
                log.warning("google cal sync block %s: %s", bid, e)
                errors.append(f"block {bid}: {e}")

    ok = created + updated > 0 and len(errors) == 0
    hint = (
        "Events are on Google Calendar (primary). Look for titles like "
        "'AI/ML study block', 'Bible / devotion'. Enable phone/Zepp calendar sync for Amazfit."
        if ok
        else (
            "Nothing was written. Enable Google Calendar API, reconnect Google, then Push again. "
            "Or use Download .ics → Import in Google Calendar."
            if errors or created + updated == 0
            else "Partial sync — check errors."
        )
    )
    return {
        "ok": ok,
        "calendar_id": cal_id,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:8],
        "error": errors[0] if errors and not ok else None,
        "hint": hint,
    }


def disconnect_google() -> None:
    try:
        if _TOKEN_PATH.is_file():
            _TOKEN_PATH.unlink()
    except Exception:
        pass
