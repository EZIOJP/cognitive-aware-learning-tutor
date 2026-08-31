"""Device-wide domain block via OS hosts file (all apps — Edge, Cursor browser, etc.).

Windows: ``C:\\Windows\\System32\\drivers\\etc\\hosts`` (admin required to write).
Uses the same seed lists as ``browser_gate_policy`` so browser + device stay aligned.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.behavior.browser_gate_policy import (
    DEFAULT_PORN_DOMAINS,
    DEFAULT_SOCIAL_DOMAINS,
)

log = logging.getLogger("calt.device_block")

MARK_BEGIN = "# BEGIN CALT-DEVICE-BLOCK"
MARK_END = "# END CALT-DEVICE-BLOCK"
MARK_HEADER = "# CALT device block — CALT porn-only (desktop tracker; not YouTube)"

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "block_porn": True,
    "block_watch": False,
    "block_social": False,
    "extra_domains": [],
    "source": "theporndude.com",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def settings_path() -> Path:
    p = _repo_root() / "data" / "behavior" / "device_block.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.is_file():
        return dict(DEFAULT_SETTINGS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return dict(DEFAULT_SETTINGS)
    out = dict(DEFAULT_SETTINGS)
    out.update({k: raw[k] for k in DEFAULT_SETTINGS if k in raw})
    extra = raw.get("extra_domains")
    if isinstance(extra, list):
        out["extra_domains"] = [str(x).strip().lower() for x in extra if str(x).strip()]
    return out


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    cur = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in data:
            cur[key] = data[key]
    if "extra_domains" in data and isinstance(data["extra_domains"], list):
        cur["extra_domains"] = [str(x).strip().lower() for x in data["extra_domains"] if str(x).strip()]
    settings_path().write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur


def hosts_file_path() -> Path:
    if sys.platform == "win32":
        windir = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        return windir / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


def _expand_host(domain: str) -> list[str]:
    d = (domain or "").strip().lower().removeprefix("www.")
    if not d or d in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return []
    hosts = {d, f"www.{d}"}
    return sorted(hosts)


def collect_block_domains(settings: dict[str, Any] | None = None) -> list[str]:
    s = settings or load_settings()
    out: set[str] = set()
    if s.get("block_porn", True):
        from backend.behavior import porn_blocklist as tpd

        for d in tpd.cached_domains():
            out.update(_expand_host(d))
        for d in DEFAULT_PORN_DOMAINS:
            out.update(_expand_host(d))
    if s.get("block_social", False):
        from backend.behavior.browser_gate_policy import DEFAULT_SOCIAL_DOMAINS

        for d in DEFAULT_SOCIAL_DOMAINS:
            out.update(_expand_host(d))
    if s.get("block_watch", False):
        from backend.behavior.browser_gate_policy import DEFAULT_WATCH_DOMAINS

        for d in DEFAULT_WATCH_DOMAINS:
            out.update(_expand_host(d))
    for d in s.get("extra_domains") or []:
        out.update(_expand_host(str(d)))
    return sorted(out)


def _block_lines(domains: list[str]) -> list[str]:
    lines = [MARK_HEADER, MARK_BEGIN]
    for host in domains:
        lines.append(f"0.0.0.0 {host}")
        lines.append(f"127.0.0.1 {host}")
        lines.append(f"::1 {host}")
    lines.append(MARK_END)
    return lines


def strip_managed_section(text: str) -> str:
    if MARK_BEGIN not in text:
        return text.rstrip() + "\n"
    before, rest = text.split(MARK_BEGIN, 1)
    if MARK_END in rest:
        _, after = rest.split(MARK_END, 1)
        return (before.rstrip() + "\n" + after.lstrip()).rstrip() + "\n"
    return before.rstrip() + "\n"


def merge_hosts_content(existing: str, domains: list[str]) -> str:
    base = strip_managed_section(existing)
    if not domains:
        return base
    block = "\n".join(_block_lines(domains)) + "\n"
    return base.rstrip() + "\n\n" + block


def read_hosts_file() -> str:
    path = hosts_file_path()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def hosts_section_active() -> bool:
    text = read_hosts_file()
    return MARK_BEGIN in text and MARK_END in text


def count_managed_domains() -> int:
    text = read_hosts_file()
    if MARK_BEGIN not in text or MARK_END not in text:
        return 0
    chunk = text.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]
    hosts: set[str] = set()
    for line in chunk.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] in {"0.0.0.0", "127.0.0.1", "::1"}:
            hosts.add(parts[1].lower())
    return len(hosts)


def _flush_dns() -> None:
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            timeout=15,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _disable_windows_doh() -> dict[str, Any]:
    """Prefer system DNS (hosts file) over OS/browser secure DNS on Windows."""
    if sys.platform != "win32":
        return {"ok": True, "skipped": True}
    import winreg

    results: list[str] = []
    try:
        key = winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
        )
        winreg.SetValueEx(key, "EnableAutoDoh", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        results.append("WinDNS EnableAutoDoh=0")
    except OSError as exc:
        return {"ok": False, "error": str(exc), "hint": "Run as Administrator"}

    policies: list[tuple[str, str, str, int]] = [
        (r"SOFTWARE\Policies\Microsoft\Edge", "DnsOverHttpsMode", "off", winreg.REG_SZ),
        (r"SOFTWARE\Policies\Google\Chrome", "DnsOverHttpsMode", "off", winreg.REG_SZ),
    ]
    for path, name, val, typ in policies:
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path)
            winreg.SetValueEx(key, name, 0, typ, val)
            winreg.CloseKey(key)
            results.append(f"{path}\\{name}")
        except OSError:
            pass
    return {"ok": True, "policies": results}


def verify_hostname_blocked(hostname: str = "youtube.com") -> dict[str, Any]:
    import socket

    blocked_ips = {"127.0.0.1", "0.0.0.0", "::1", "::", "0:0:0:0:0:0:0:0"}
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        ips = sorted({item[4][0] for item in infos})
        return {
            "hostname": hostname,
            "ips": ips,
            "blocked": bool(ips) and all(ip in blocked_ips for ip in ips),
        }
    except socket.gaierror:
        return {"hostname": hostname, "ips": [], "blocked": True}


def write_hosts(domains: list[str]) -> None:
    path = hosts_file_path()
    existing = read_hosts_file() if path.is_file() else ""
    merged = merge_hosts_content(existing, domains)
    path.write_text(merged, encoding="utf-8")
    _flush_dns()


def remove_hosts_block() -> None:
    path = hosts_file_path()
    if not path.is_file():
        return
    merged = merge_hosts_content(read_hosts_file(), [])
    path.write_text(merged, encoding="utf-8")
    _flush_dns()


def apply_from_settings(*, enable: bool | None = None) -> dict[str, Any]:
    settings = load_settings()
    if enable is True:
        settings = save_settings({**settings, "enabled": True})
    if not settings.get("enabled"):
        try:
            remove_hosts_block()
        except PermissionError as exc:
            return {"ok": False, "error": str(exc), "needs_admin": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "applied": False, "domain_count": 0}

    domains = collect_block_domains(settings)
    try:
        write_hosts(domains)
    except PermissionError:
        return {
            "ok": False,
            "needs_admin": True,
            "domain_count": len(domains),
            "error": "Administrator rights required to edit the hosts file.",
            "apply_script": "scripts\\device_block_apply.bat",
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc), "domain_count": len(domains)}

    log.info("device_block applied %s domains", len(domains))
    doh = _disable_windows_doh()
    sample = "pornhub.com" if "pornhub.com" in domains else (domains[0] if domains else "")
    verify = verify_hostname_blocked(sample) if sample else None
    return {
        "ok": True,
        "applied": True,
        "domain_count": len(domains),
        "verify_sample": verify,
        "doh_policy": doh,
        "effective": bool(verify.get("blocked")) if verify else True,
    }


def remove_all() -> dict[str, Any]:
    save_settings({**load_settings(), "enabled": False})
    try:
        remove_hosts_block()
    except PermissionError:
        return {
            "ok": False,
            "needs_admin": True,
            "error": "Administrator rights required to edit the hosts file.",
            "apply_script": "scripts\\device_block_apply.bat",
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "applied": False, "domain_count": 0}


def status() -> dict[str, Any]:
    settings = load_settings()
    domains = collect_block_domains(settings) if settings.get("enabled") else []
    active = hosts_section_active()
    return {
        "platform": platform.system(),
        "hosts_path": str(hosts_file_path()),
        "settings": settings,
        "active": active,
        "configured_domain_count": len(domains),
        "managed_host_entries": count_managed_domains(),
        "needs_sync": bool(settings.get("enabled")) != active
        or (settings.get("enabled") and count_managed_domains() != len(domains)),
        "verify_sample": verify_hostname_blocked("pornhub.com") if active else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def maybe_sync_on_gate(*, gate_locked: bool) -> None:
    """Legacy hook — tracker uses tracker_porn_block.tracker_sync_porn_hosts."""
    settings = load_settings()
    if not settings.get("enabled"):
        return
    st = status()
    if st.get("needs_sync"):
        apply_from_settings()
