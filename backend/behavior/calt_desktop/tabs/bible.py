"""Bible tab — open reader + morning status."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

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
        lay.addWidget(self._info)
        btn = QPushButton("Open Bible reader (web)")
        btn.clicked.connect(lambda: webbrowser.open(BIBLE_URL))
        lay.addWidget(btn)
        tip = QLabel(
            "Mark chapters done in the reader. Desktop will later embed the PDF; "
            "for now the web reader writes the same progress files."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._info.setText("Waiting for tracker user…")
            return
        try:
            from backend.bible import store as bible_store

            s = bible_store.summary(uid)
            chapters = s.get("chapters_completed_today") or []
            goal = (s.get("chapter_goal") or {}).get("met")
            self._info.setText(
                f"Chapters today: {', '.join(chapters) if chapters else '(none)'}\n"
                f"Goal met: {bool(goal) or len(chapters) >= 1}"
            )
        except Exception as exc:  # noqa: BLE001
            self._info.setText(f"Could not load bible status: {exc}")
