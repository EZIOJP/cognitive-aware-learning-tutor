"""Watch ↔ PC hub setup (CALT Sync + CALT Voice)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.constants import HUB_HEALTH_URL

DEFAULT_TOKEN = "calt-local-wearables"


def probe_hub_health(url: str = HUB_HEALTH_URL, *, timeout: float = 2.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            return {"ok": True, "status": resp.status, "body": data if isinstance(data, dict) else {}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def lan_base_hint() -> str:
    try:
        from backend.community.network import lan_ipv4

        ip = lan_ipv4()
        if ip:
            return f"http://{ip}:8765"
    except Exception:  # noqa: BLE001
        pass
    return "http://<PC-LAN-IP>:8765"


class WatchTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Watch ↔ PC (CALT Sync + CALT Voice)"))
        self._health = QLabel("Hub: …")
        self._health.setWordWrap(True)
        self._health.setStyleSheet("font-size: 14px; font-weight: 600;")
        lay.addWidget(self._health)

        self._setup = QTextEdit()
        self._setup.setReadOnly(True)
        self._setup.setMaximumHeight(220)
        lay.addWidget(self._setup)

        row = QHBoxLayout()
        btn = QPushButton("Refresh hub health")
        btn.clicked.connect(self.refresh)
        row.addWidget(btn)
        row.addStretch(1)
        lay.addLayout(row)
        tip = QLabel(
            "Sideload: packages\\calt-zepp\\sideload.bat · packages\\calt-voice\\sideload.bat\n"
            "Phone must use the PC LAN IP — never localhost."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(10_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        base = lan_base_hint()
        probe = probe_hub_health()
        if probe.get("ok"):
            body = probe.get("body") or {}
            self._health.setText(
                f"Hub OK · {body.get('service', 'calt.tracker_hub')} · "
                f"port {body.get('port', 8765)}"
            )
            self._health.setStyleSheet("font-size: 14px; font-weight: 600; color: #34d399;")
        else:
            self._health.setText(f"Hub down — {probe.get('error')}")
            self._health.setStyleSheet("font-size: 14px; font-weight: 600; color: #f87171;")

        self._setup.setPlainText(
            "Phone Zepp settings (both apps):\n"
            f"  Base URL — {base}\n"
            f"  Token    — {DEFAULT_TOKEN}\n\n"
            "Local check: " + HUB_HEALTH_URL + "\n"
            "CALT Sync: Test PC → Dump today → Send queue (fill-forward watermark).\n"
            "CALT Voice: Record → Files → send; clips land in data/voice_notes/."
        )
