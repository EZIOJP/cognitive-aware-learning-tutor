"""Watch ↔ PC hub setup (CALT Sync + CALT Voice).

Wearables sync is **manual only**: Dump → Send on the watch. This tab never
auto-polls ingest — Refresh sync status is an explicit button (and one load on open).
"""

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
from backend.behavior.calt_desktop.sync_status import (
    voice_sync_summary,
    wearables_sync_summary,
)

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
    """Manual wearables status — no timer. Sync happens on the watch Dump→Send."""

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Watch ↔ PC (CALT Sync + CALT Voice)"))
        self._health = QLabel("Hub: …")
        self._health.setWordWrap(True)
        self._health.setStyleSheet("font-size: 14px; font-weight: 600;")
        lay.addWidget(self._health)

        self._wear_sync = QLabel("CALT Sync last: …")
        self._wear_sync.setWordWrap(True)
        lay.addWidget(self._wear_sync)

        self._voice_sync = QLabel("CALT Voice last upload: …")
        self._voice_sync.setWordWrap(True)
        lay.addWidget(self._voice_sync)

        self._setup = QTextEdit()
        self._setup.setReadOnly(True)
        self._setup.setMaximumHeight(240)
        lay.addWidget(self._setup)

        row = QHBoxLayout()
        self._sync_btn = QPushButton("Refresh sync status")
        self._sync_btn.clicked.connect(self.refresh)
        row.addWidget(self._sync_btn)
        row.addStretch(1)
        lay.addLayout(row)
        tip = QLabel(
            "Wearables = manual only (no auto poll).\n"
            "Watch: Test PC → Dump today → Send queue.\n"
            "Sideload: packages\\calt-zepp\\sideload.bat · packages\\calt-voice\\sideload.bat\n"
            "Phone must use the PC LAN IP — never localhost."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)

        QTimer.singleShot(0, self.refresh)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # One status read when the tab is opened — never a repeating timer.
        QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        base = lan_base_hint()
        probe = probe_hub_health()
        wear_at, wear_detail = wearables_sync_summary()
        voice_at, voice_detail = voice_sync_summary()

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

        self._wear_sync.setText(f"CALT Sync last: {wear_at} — {wear_detail}")
        self._wear_sync.setStyleSheet(
            "color: #34d399;" if wear_at != "never" else "color: #94a3b8;"
        )

        self._voice_sync.setText(f"CALT Voice last upload: {voice_at} — {voice_detail}")
        self._voice_sync.setStyleSheet(
            "color: #34d399;" if voice_at != "never" else "color: #94a3b8;"
        )

        hub_line = "Hub up — phone can reach PC." if probe.get("ok") else (
            "Hub down — start desktop tracker; phone uploads will fail until hub is up."
        )
        self._sync_btn.setText(
            f"Refresh sync status · wearables {wear_at} · voice {voice_at}"
        )

        self._setup.setPlainText(
            "Wearables sync is MANUAL — this app does not pull the watch.\n"
            "On the watch: Dump today → Send queue (after Test PC).\n\n"
            "Phone Zepp settings (both apps):\n"
            f"  Base URL — {base}\n"
            f"  Token    — {DEFAULT_TOKEN}\n\n"
            "Local check: " + HUB_HEALTH_URL + "\n"
            f"{hub_line}\n\n"
            "CALT Voice: open clock → tap to record → Files → tap clip to send.\n"
            "Clips land in data/voice_notes/ after VN_FINISH succeeds on the hub."
        )
