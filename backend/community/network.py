"""Tailscale / LAN reachability and SSRF-safe peer URLs."""

from __future__ import annotations

import ipaddress
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_WIN_TAILSCALE = Path(r"C:\Program Files\Tailscale\tailscale.exe")


def public_base_from_peer(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    host = parsed.hostname
    port = parsed.port
    if parsed.scheme == "http":
        port = port or 8000
        netloc = f"{host}:{port}" if port != 80 else host
    else:
        netloc = f"{host}:{port}" if port and port != 443 else host
    return f"{parsed.scheme}://{netloc}"


def peer_url_allowed(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host.endswith(".ts.net") or host.endswith(".tailscale.net"):
        return True
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip in TAILSCALE_CGNAT)


def lan_ipv4() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def _bundle(host: str) -> dict[str, str]:
    return {
        "site": f"http://{host}:5173",
        "api": f"http://{host}:8000",
        "wearables": f"http://{host}:8765",
    }


def device_urls(ts: dict[str, Any] | None = None) -> dict[str, Any]:
    """LAN + Tailscale URLs for the whole site (:5173), API, and wearables hub."""
    ts = ts or {}
    lan = lan_ipv4()
    hosts: list[str] = []
    for ip in ts.get("ipv4") or []:
        if ip and ip not in hosts:
            hosts.append(str(ip))
    magic = ts.get("magicdns")
    if magic and magic not in hosts:
        hosts.append(str(magic))
    tail = [_bundle(h) for h in hosts]
    lan_b = _bundle(lan) if lan else None
    return {
        "lan": lan_b,
        "tailscale": tail,
        "lan_site": lan_b["site"] if lan_b else None,
        "lan_api": lan_b["api"] if lan_b else None,
        "lan_wearables": lan_b["wearables"] if lan_b else None,
        "tailscale_site": [b["site"] for b in tail],
        "tailscale_api": [b["api"] for b in tail],
        "tailscale_wearables": [b["wearables"] for b in tail],
    }


def _tailscale_bin() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    if _WIN_TAILSCALE.is_file():
        return str(_WIN_TAILSCALE)
    return None


def tailscale_status() -> dict[str, Any]:
    exe = _tailscale_bin()
    if not exe:
        return {
            "installed": False,
            "running": False,
            "ipv4": [],
            "magicdns": None,
            "hint": "Install Tailscale on this PC and your phone. Then paste a friend's 100.x:8000 URL below. Ranks stay off until you opt in.",
        }
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": 4,
        "check": False,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        ip_run = subprocess.run([exe, "ip", "-4"], **kwargs)
        ips = [line.strip() for line in (ip_run.stdout or "").splitlines() if line.strip()]
        magic = None
        st = subprocess.run([exe, "status", "--json"], **kwargs)
        if st.returncode == 0 and st.stdout:
            payload = json.loads(st.stdout)
            self_node = payload.get("Self") or {}
            magic = (self_node.get("DNSName") or "").rstrip(".") or None
        running = ip_run.returncode == 0 and bool(ips)
        hint = (
            "Use the Tailscale *site* URL on your phone browser — full CALT, not just the API."
            if running
            else "Tailscale is installed but not connected. Open the Tailscale app on this PC, then retry."
        )
        return {
            "installed": True,
            "running": running,
            "ipv4": ips,
            "magicdns": magic,
            "hint": hint,
        }
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {
            "installed": True,
            "running": False,
            "ipv4": [],
            "magicdns": None,
            "hint": "Could not read Tailscale. Open the Tailscale app, then retry.",
        }
