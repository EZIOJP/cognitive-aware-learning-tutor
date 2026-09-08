"""Dashboard tab — QWebEngineView when available, else Qt text fallback."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.dashboard_bridge import snapshot_from_gate
from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import primary_button
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"

_WEB_ENGINE = False
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore

    _WEB_ENGINE = True
except Exception:  # noqa: BLE001
    QWebEngineView = None  # type: ignore[misc, assignment]


def web_engine_available() -> bool:
    return bool(_WEB_ENGINE and QWebEngineView is not None)


class WebViewDashboard(VisiblePollMixin, QWidget):
    """First-tab Focus dashboard: live gate → why / until / blocked summary."""

    REFRESH_MS = 8_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self._use_web = web_engine_available()
        self._view: Any = None
        self._fallback: QTextBrowser | None = None
        self._status: QLabel | None = None
        self._btn_free: QPushButton | None = None
        self._btn_spend: QPushButton | None = None
        self._last_actions: dict[str, Any] = {}
        self._last_earned: dict[str, Any] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        if self._use_web:
            self._view = QWebEngineView(self)
            url = QUrl.fromLocalFile(str(_DASHBOARD_HTML.resolve()))
            self._view.load(url)
            lay.addWidget(self._view, stretch=1)
            self._view.loadFinished.connect(lambda _ok: self.refresh())
            try:
                self._view.urlChanged.connect(self._on_web_url)
            except Exception:  # noqa: BLE001
                pass
        else:
            title = QLabel("CALT Desktop · Focus")
            title.setObjectName("hero")
            lay.addWidget(title)
            hint = QLabel(
                "Qt panel fallback (PySide6 WebEngine not installed). "
                "Same live gate fields as the WebView dashboard."
            )
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            lay.addWidget(hint)
            self._fallback = QTextBrowser()
            self._fallback.setOpenExternalLinks(False)
            lay.addWidget(self._fallback, stretch=1)
            self._status = QLabel("")
            self._status.setObjectName("muted")
            lay.addWidget(self._status)

        lay.addLayout(self._build_action_row())
        self._init_visible_poll()

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for label, tab in (
            ("Rules", "Rules"),
            ("Schedules", "Schedules"),
            ("Device", "Device"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("navChip")
            btn.clicked.connect(lambda _c=False, t=tab: go_tab(t))
            row.addWidget(btn)
        self._btn_free = primary_button("Free time (PIN)…")
        self._btn_free.clicked.connect(self._on_free_time)
        row.addWidget(self._btn_free)
        self._btn_spend = primary_button("Spend earned…")
        self._btn_spend.clicked.connect(self._on_spend_earned)
        self._btn_spend.setEnabled(False)
        row.addWidget(self._btn_spend)
        if not self._use_web:
            refresh = QPushButton("Refresh")
            refresh.setObjectName("navChip")
            refresh.clicked.connect(self.refresh)
            row.addWidget(refresh)
        row.addStretch(1)
        return row

    def _on_web_url(self, url: QUrl) -> None:
        """HTML CTAs use calt://action/… — intercept without leaving the page."""
        if url.scheme() != "calt":
            return
        host = (url.host() or "").lower()
        path = (url.path() or "").strip("/").lower()
        action = host or path
        if action in ("rules", "go/rules"):
            go_tab("Rules")
        elif action in ("schedules", "go/schedules"):
            go_tab("Schedules")
        elif action in ("device", "go/device"):
            go_tab("Device")
        elif action in ("free", "pin", "free-time"):
            self._on_free_time()
        elif action in ("spend", "spend-earned", "earned"):
            self._on_spend_earned()
        if self._view is not None:
            try:
                self._view.setUrl(QUrl.fromLocalFile(str(_DASHBOARD_HTML.resolve())))
            except Exception:  # noqa: BLE001
                pass

    def _on_free_time(self) -> None:
        actions = self._last_actions
        if actions.get("incubation_blocks_pin"):
            QMessageBox.information(
                self,
                "Free time",
                "Incubation break is active — PIN free time is paused until it ends.",
            )
            return
        if not actions.get("can_pin_free", True):
            QMessageBox.information(
                self,
                "Free time",
                "Free time is not available right now (gate off or override already active).",
            )
            return
        from backend.behavior.calt_desktop.dialogs import prompt_free_time

        if prompt_free_time(self):
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.refresh()

    def _on_spend_earned(self) -> None:
        actions = self._last_actions
        if actions.get("incubation_blocks_pin"):
            QMessageBox.information(
                self,
                "Spend earned",
                "Incubation break is active — spending is paused until it ends.",
            )
            return
        if not actions.get("can_spend_earned"):
            QMessageBox.information(
                self,
                "Spend earned",
                "No earned free minutes available right now.",
            )
            return
        from backend.behavior.calt_desktop.dialogs import prompt_spend_earned

        if prompt_spend_earned(self, user_id=int(self._service.user_id or 0)):
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.refresh()

    def _current_snapshot(self) -> dict[str, Any]:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if uid > 0:
            try:
                from backend.behavior.calt_desktop.dashboard_bridge import (
                    snapshot_for_user,
                )

                return snapshot_for_user(uid)
            except Exception:  # noqa: BLE001
                pass
        try:
            gate = self._service.latest_gate() or {}
        except Exception:  # noqa: BLE001
            gate = {}
        return snapshot_from_gate(gate)

    def refresh(self) -> None:
        snap = self._current_snapshot()
        actions = snap.get("actions") if isinstance(snap.get("actions"), dict) else {}
        earned = snap.get("earned") if isinstance(snap.get("earned"), dict) else {}
        self._last_actions = dict(actions)
        self._last_earned = dict(earned)
        can_pin = bool(actions.get("can_pin_free")) and not bool(
            actions.get("incubation_blocks_pin")
        )
        can_spend = bool(actions.get("can_spend_earned")) and int(
            earned.get("balance_minutes") or 0
        ) > 0
        if self._btn_free is not None:
            self._btn_free.setEnabled(can_pin)
            tip = (
                "Incubation blocks PIN free time"
                if actions.get("incubation_blocks_pin")
                else (
                    "Grant temporary free browse (PIN)"
                    if can_pin
                    else "Unavailable (gate off or free override already on)"
                )
            )
            self._btn_free.setToolTip(tip)
        if self._btn_spend is not None:
            self._btn_spend.setEnabled(can_spend)
            self._btn_spend.setToolTip(
                "Spend earned free minutes (PIN)"
                if can_spend
                else "Earn minutes via Bible / plan / daily goal first"
            )

        if self._use_web and self._view is not None:
            payload = json.dumps(snap, ensure_ascii=True)
            js = f"window.__caltApplySnapshot && window.__caltApplySnapshot({payload});"
            try:
                self._view.page().runJavaScript(js)
            except Exception:  # noqa: BLE001
                pass
            return
        self._render_fallback(snap)

    def _render_fallback(self, snap: dict[str, Any]) -> None:
        if self._fallback is None:
            return
        active = snap.get("active") if isinstance(snap.get("active"), dict) else {}
        until = active.get("until") if isinstance(active.get("until"), dict) else {}
        blocked = active.get("blocked_summary") or []
        if not isinstance(blocked, list):
            blocked = []
        earned = snap.get("earned") if isinstance(snap.get("earned"), dict) else {}
        inc = snap.get("incubation") if isinstance(snap.get("incubation"), dict) else {}

        lines = [
            f"<h2>{html.escape(str(active.get('browser_mode_label') or '—'))}</h2>",
            f"<p><b>Hard block:</b> "
            f"{'armed' if active.get('hard_block_armed') else 'off'} · "
            f"<b>Morning next:</b> {html.escape(str(active.get('morning_next') or '—'))}</p>",
            f"<p style='font-size:15px'>{html.escape(str(active.get('why') or ''))}</p>",
            f"<p style='color:#10b981'>{html.escape(str(until.get('label') or ''))}</p>",
            "<h3>Blocked</h3><ul>",
        ]
        for item in blocked:
            lines.append(f"<li>{html.escape(str(item))}</li>")
        lines.append("</ul>")
        if inc.get("active"):
            lines.append(
                "<h3>Incubation</h3>"
                f"<p>{int(inc.get('remaining_sec') or 0)}s left of "
                f"{int(inc.get('total_sec') or 0)}s</p>"
            )
        lines.append(
            "<h3>Earned free time</h3>"
            f"<p>Balance {int(earned.get('balance_minutes') or 0)} min · "
            f"Today {int(earned.get('daily_earned') or 0)} / "
            f"{int(earned.get('daily_cap') or 60)}</p>"
        )
        enf = snap.get("enforcer") if isinstance(snap.get("enforcer"), dict) else {}
        if enf:
            status = (
                "owns kills+track"
                if enf.get("owns")
                else (
                    "service up"
                    if enf.get("service_running") is True
                    else ("built" if enf.get("exe_built") else "not built")
                )
            )
            kill = str(enf.get("last_kill") or "").strip()
            lines.append(
                "<h3>Native enforcer</h3>"
                f"<p>{html.escape(status)}</p>"
                f"<p style='color:#94a3b8;font-size:13px'>"
                f"{html.escape(kill or 'No kills logged yet.')}</p>"
            )
        self._fallback.setHtml("\n".join(lines))
        if self._status is not None:
            self._status.setText("Updated from live gate")
