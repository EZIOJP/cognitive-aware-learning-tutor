"""Bible tab — today's chapter + mark done (same store as web reader)."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

BIBLE_URL = "http://localhost:5173/bible"


class BibleTab(QWidget):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Morning Bible"))
        self._info = QLabel("…")
        self._info.setWordWrap(True)
        self._info.setStyleSheet("font-size: 14px;")
        lay.addWidget(self._info)

        btn_done = QPushButton("Mark today's chapter done")
        btn_done.clicked.connect(self.mark_done)
        lay.addWidget(btn_done)

        btn = QPushButton("Open full Bible reader (web)")
        btn.clicked.connect(lambda: webbrowser.open(BIBLE_URL))
        lay.addWidget(btn)

        tip = QLabel(
            "Marking done here updates the same day files as the web reader.\n"
            "Use the web reader to read the chapter text; use this button to clear the morning gate."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(8000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._info.setText("Waiting for tracker user…")
            return
        try:
            from backend.bible import store as bible_store

            today = bible_store.resolve_today_chapter(uid)
            s = bible_store.summary(uid)
            chapters = s.get("chapters_completed_today") or []
            done = bool(today.get("done")) or today.get("key") in chapters
            self._info.setText(
                f"Today's chapter: {today.get('label') or '?'}\n"
                f"Done: {'yes' if done else 'no'}\n"
                f"Completed today: {', '.join(chapters) if chapters else '(none)'}"
            )
        except Exception as exc:  # noqa: BLE001
            self._info.setText(f"Could not load bible status: {exc}")

    def mark_done(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            QMessageBox.warning(self, "Bible", "No tracker user yet.")
            return
        try:
            from backend.bible import store as bible_store
            from backend.planner import morning_rewards as morning_rewards_store

            today = bible_store.resolve_today_chapter(uid)
            book = str(today.get("book") or "")
            chapter = int(today.get("chapter") or 1)
            bible_store.tick_chapter(uid, book=book, chapter=chapter, done=True)
            try:
                morning_rewards_store.maybe_grant_bible(uid)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.refresh()
            QMessageBox.information(
                self,
                "Bible",
                f"Marked {today.get('label')} done. Next: confirm plan (Plan tab).",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Bible", str(exc))
