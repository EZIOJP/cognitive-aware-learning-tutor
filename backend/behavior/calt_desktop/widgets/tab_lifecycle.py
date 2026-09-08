"""Tab lifecycle helpers — lazy build + poll only while visible."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class VisiblePollMixin:
    """Start refresh timer on show; defer work so tab switches stay instant."""

    REFRESH_MS: int = 8000

    def _init_visible_poll(self, refresh: Callable[[], None] | None = None) -> None:
        cb = refresh or getattr(self, "refresh", None)
        if cb is None:
            raise TypeError(f"{type(self).__name__} needs refresh() or a callback")
        self._vis_poll_cb = cb
        self._vis_poll = QTimer(self)  # type: ignore[attr-defined]
        self._vis_poll.setInterval(self.REFRESH_MS)
        self._vis_poll.timeout.connect(cb)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[misc]
        self._vis_poll.start()
        QTimer.singleShot(0, self._vis_poll_cb)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)  # type: ignore[misc]
        self._vis_poll.stop()


class DeferredTab(QWidget):
    """Placeholder tab; builds the real widget on first show (deferred one tick)."""

    def __init__(self, factory: Callable[[], QWidget], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._content: QWidget | None = None
        self._building = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder: QLabel | None = None

    def ensure(self) -> QWidget | None:
        return self._content

    def warm(self) -> None:
        """Build content off-screen so first visit is instant."""
        if self._content is None and not self._building:
            self._building = True
            self._build()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._content is not None or self._building:
            return
        self._building = True
        self._placeholder = QLabel("Loading…")
        self._placeholder.setObjectName("muted")
        self._layout.addWidget(self._placeholder)
        QTimer.singleShot(0, self._build)

    def _build(self) -> None:
        try:
            self._content = self._factory()
            if self._placeholder is not None:
                self._placeholder.hide()
                self._placeholder.deleteLater()
                self._placeholder = None
            self._layout.addWidget(self._content)
        finally:
            self._building = False
