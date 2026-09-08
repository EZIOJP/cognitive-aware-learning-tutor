"""Native day/week calendar (no WebEngine — fast, offline)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

HOUR_HEIGHT = 44
LEFT_GUTTER = 54

_CATEGORY_COLORS: dict[str, str] = {
    "coding practice": "#0d9488",
    "ai / ml": "#6366f1",
    "study / reading": "#059669",
    "coursework (browser)": "#2563eb",
    "study": "#10b981",
    "lecture": "#8b5cf6",
    "review": "#f59e0b",
    "break": "#64748b",
    "personal": "#ec4899",
}


def parse_iso_local(iso: str | None) -> datetime | None:
    if not iso:
        return None
    raw = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def block_local_span(block: dict, day: date) -> tuple[int, int] | None:
    """Minutes from midnight on *day* for start/end (clipped to the day)."""
    start_dt = parse_iso_local(str(block.get("start_at") or ""))
    end_dt = parse_iso_local(str(block.get("end_at") or ""))
    if start_dt is None or end_dt is None:
        return None
    day_start = datetime(day.year, day.month, day.day, tzinfo=start_dt.tzinfo)
    day_end = day_start.replace(hour=23, minute=59, second=59)
    if end_dt <= day_start or start_dt > day_end:
        return None
    clip_start = max(start_dt, day_start)
    clip_end = min(end_dt, day_end.replace(hour=23, minute=59))
    sm = clip_start.hour * 60 + clip_start.minute
    em = clip_end.hour * 60 + clip_end.minute
    if em <= sm:
        em = min(24 * 60, sm + max(15, int(block.get("planned_minutes") or 30)))
    return sm, em


def category_color(category: str) -> QColor:
    key = (category or "study").strip().lower()
    hex_c = _CATEGORY_COLORS.get(key, "#334155")
    return QColor(hex_c)


class DayTimelineWidget(QWidget):
    """Scrollable 24h grid with planner blocks."""

    block_activated = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day = date.today()
        self._blocks: list[dict] = []
        self._hit_regions: list[tuple[int, int, int, int, int]] = []
        self.setMinimumHeight(24 * HOUR_HEIGHT)
        self.setMinimumWidth(320)
        self.setMouseTracking(True)

    def set_data(self, day: date, blocks: list[dict]) -> None:
        self._day = day
        self._blocks = list(blocks)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        self._hit_regions.clear()

        p.fillRect(self.rect(), QColor("#0f172a"))

        for hour in range(24):
            y = hour * HOUR_HEIGHT
            p.setPen(QColor(30, 41, 59))
            p.drawLine(LEFT_GUTTER, y, w, y)
            p.setPen(QColor(100, 116, 139))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(4, y + 16, f"{hour:02d}:00")

        col_w = max(120, w - LEFT_GUTTER - 8)
        for block in self._blocks:
            span = block_local_span(block, self._day)
            if span is None:
                continue
            sm, em = span
            y1 = int((sm / 60.0) * HOUR_HEIGHT)
            y2 = int((em / 60.0) * HOUR_HEIGHT)
            h = max(20, y2 - y1)
            x = LEFT_GUTTER + 4
            color = category_color(str(block.get("category") or ""))
            status = str(block.get("status") or "")
            if status == "done":
                color = QColor("#166534")
            elif status == "in_progress":
                color = QColor("#0e7490")

            p.setBrush(color)
            p.setPen(QColor(255, 255, 255, 40))
            p.drawRoundedRect(x, y1, col_w, h, 6, 6)

            title = str(block.get("title") or "Untitled")
            time_s = f"{block.get('start_local', '?')}–{block.get('end_local', '?')}"
            p.setPen(QColor("#f8fafc"))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.drawText(x + 8, y1 + 14, col_w - 16, 16, Qt.AlignmentFlag.AlignLeft, title)
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor("#e2e8f0"))
            p.drawText(x + 8, y1 + 28, col_w - 16, 14, Qt.AlignmentFlag.AlignLeft, time_s)

            bid = int(block.get("id") or 0)
            self._hit_regions.append((x, y1, col_w, h, bid))

        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        px, py = int(event.position().x()), int(event.position().y())
        for x, y, cw, ch, bid in self._hit_regions:
            if x <= px <= x + cw and y <= py <= y + ch:
                self.block_activated.emit(bid)
                return


class NativeCalendarPanel(QWidget):
    """Day timeline inside a scroll area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._timeline = DayTimelineWidget()
        scroll.setWidget(self._timeline)
        lay.addWidget(scroll)

    def timeline(self) -> DayTimelineWidget:
        return self._timeline

    def set_data(self, day: date, blocks: list[dict]) -> None:
        self._timeline.set_data(day, blocks)
