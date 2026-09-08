"""Native 2D day grid — plan + actual bands, click for details.

Render model (each visible hour = one row):
  X axis: minutes 0–60 within that hour (left = :00, right = :60).
  Y axis: one row per clock hour (only hours with plan/actual data shown).

  Each row splits into two bands:
    Top ~42%  — tracked actual (blue pills, up to 3 lanes)
    Bottom    — plan blocks from DB (colored bars by category)

  Plan blocks longer than 1 hour are split into segments per hour in
  planner_segments.plan_blocks_to_hour_segs; text shows on each segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.planner_segments import segs_by_hour
from backend.behavior.calt_desktop.theme import muted_label

ROW_H = 76
AXIS_H = 40
LEFT_GUTTER = 58
MIN_PLAN_W = 14
MIN_PLAN_H = 26
MIN_ACTUAL_H = 10
MAX_ACTUAL_LANES = 3
_PAD_X = 6

_CATEGORY_COLORS: dict[str, str] = {
    "coding practice": "#0d9488",
    "ai / ml": "#6366f1",
    "study / reading": "#059669",
    "coursework (browser)": "#2563eb",
    "study": "#10b981",
    "spiritual": "#7c3aed",
    "food": "#d97706",
    "lecture": "#8b5cf6",
    "review": "#f59e0b",
    "break": "#64748b",
    "personal": "#ec4899",
}

_ACTUAL_PALETTE = ["#38bdf8", "#a78bfa", "#fb923c", "#4ade80", "#f472b6", "#94a3b8"]

_LABEL_ALIASES: dict[str, str] = {
    "cursor": "Cursor",
    "python": "Python",
    "chrome": "Chrome",
    "firefox": "Firefox",
    "code": "VS Code",
    "netflix": "Netflix",
    "youtube": "YouTube",
    "discord": "Discord",
    "spotify": "Spotify",
}


def _format_seg_time(hour: int, start_min: int, end_min: int) -> str:
    sm = max(0, min(59, int(start_min)))
    em = max(sm + 1, min(60, int(end_min)))
    if em >= 60:
        return f"{hour:02d}:{sm:02d}–{(hour + 1) % 24:02d}:00"
    return f"{hour:02d}:{sm:02d}–{hour:02d}:{em:02d}"


def _short_label(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low in _LABEL_ALIASES:
        return _LABEL_ALIASES[low]
    if low.endswith(".exe"):
        base = s[:-4]
        key = base.lower()
        if key in _LABEL_ALIASES:
            return _LABEL_ALIASES[key]
        return base[:1].upper() + base[1:10]
    if "." in s:
        part = s.split(".")[0].lower()
        if part in _LABEL_ALIASES:
            return _LABEL_ALIASES[part]
        return part[:12].title()
    return s[:16]


def _pick_font_size(width: int, height: int, *, two_line: bool) -> int:
    if two_line:
        if width >= 160 and height >= 32:
            return 9
        if width >= 110 and height >= 28:
            return 8
        return 7
    if width >= 140:
        return 9
    if width >= 90:
        return 8
    if width >= 56:
        return 7
    return 6


def _text_fits(fm: QFontMetrics, text: str, max_w: int) -> bool:
    return bool(text) and fm.horizontalAdvance(text) <= max_w


def _draw_bar_text(
    p: QPainter,
    rect: QRect,
    *,
    title: str,
    subtitle: str = "",
    light_on_dark: bool = True,
    two_line: bool = False,
) -> None:
    """Draw title (+ optional time line) centered in a bar with elision."""
    if rect.width() < 28 or rect.height() < 10 or not title:
        return

    inner = rect.adjusted(_PAD_X, 2, -_PAD_X, -2)
    max_w = max(8, inner.width())
    title_color = QColor("#f8fafc" if light_on_dark else "#0f172a")
    sub_color = QColor(226, 232, 240, 200 if light_on_dark else 180)

    if two_line and subtitle and inner.height() >= 26 and max_w >= 72:
        size = _pick_font_size(max_w, inner.height(), two_line=True)
        title_font = QFont("Segoe UI", size, QFont.Weight.DemiBold)
        sub_font = QFont("Segoe UI", max(6, size - 1))
        fm_t = QFontMetrics(title_font)
        fm_s = QFontMetrics(sub_font)
        elided_title = fm_t.elidedText(title, Qt.TextElideMode.ElideRight, max_w)
        elided_sub = fm_s.elidedText(subtitle, Qt.TextElideMode.ElideRight, max_w)
        title_h = fm_t.height()
        sub_h = fm_s.height()
        gap = 1
        total = title_h + gap + sub_h
        y0 = inner.top() + max(0, (inner.height() - total) // 2)
        p.setFont(title_font)
        p.setPen(title_color)
        p.drawText(
            QRect(inner.left(), y0, inner.width(), title_h),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided_title,
        )
        p.setFont(sub_font)
        p.setPen(sub_color)
        p.drawText(
            QRect(inner.left(), y0 + title_h + gap, inner.width(), sub_h),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided_sub,
        )
        return

    size = _pick_font_size(max_w, inner.height(), two_line=False)
    font = QFont("Segoe UI", size, QFont.Weight.DemiBold)
    fm = QFontMetrics(font)
    line = title if _text_fits(fm, title, max_w) else fm.elidedText(title, Qt.TextElideMode.ElideRight, max_w)
    if fm.horizontalAdvance(line) > max_w:
        return
    p.setFont(font)
    p.setPen(title_color)
    p.drawText(
        inner,
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
        line,
    )


@dataclass
class _GridHit:
    rect: QRect
    kind: Literal["plan", "actual"]
    payload: dict[str, Any]
    hour: int
    tooltip: str = ""


def _cat_color(category: str) -> QColor:
    return QColor(_CATEGORY_COLORS.get((category or "").lower(), "#475569"))


def _visible_hour_range(
    plan_by_hour: dict[int, list],
    hour_slices: dict[int, dict],
) -> tuple[int, int]:
    hours: set[int] = set()
    for h, segs in plan_by_hour.items():
        if segs:
            hours.add(int(h))
    for h, sl in hour_slices.items():
        if sl and (sl.get("segments") or []):
            hours.add(int(h))
    if not hours:
        return 6, 22
    lo = max(0, min(hours) - 1)
    hi = min(23, max(hours) + 1)
    if hi - lo < 9:
        mid = (lo + hi) // 2
        lo = max(0, mid - 4)
        hi = min(23, lo + 9)
    return lo, hi


def _fmt_minutes(m: int) -> str:
    h, mins = divmod(max(0, int(m)), 60)
    if h and mins:
        return f"{h}h {mins}m"
    if h:
        return f"{h}h"
    return f"{mins}m"


class CalendarLegend(QWidget):
    """Compact color key for plan categories + actual band."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        for label, color in (
            ("Plan blocks", "#d97706"),
            ("Tracked actual", "#38bdf8"),
            ("Done", "#166534"),
        ):
            chip = QFrame()
            chip.setFixedSize(12, 12)
            chip.setStyleSheet(
                f"background: {color}; border-radius: 3px; border: 1px solid rgba(255,255,255,0.15);"
            )
            lay.addWidget(chip)
            lay.addWidget(muted_label(label))
        lay.addStretch(1)


class CalendarSummaryBar(QWidget):
    """One-line day stats above the grid."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(20)
        self._planned = self._stat_card("Planned", "—")
        self._actual = self._stat_card("Tracked", "—")
        self._blocks = self._stat_card("Blocks", "—")
        for w in (self._planned, self._actual, self._blocks):
            lay.addWidget(w)
        lay.addStretch(1)
        hint = muted_label("Click any bar for full timestamps · swipe scroll for hours")
        lay.addWidget(hint)

    def _stat_card(self, title: str, value: str) -> QWidget:
        box = QFrame()
        box.setObjectName("glossPanel")
        box.setStyleSheet(
            "QFrame#glossPanel { background: rgba(30,41,59,0.55); border-radius: 10px; "
            "padding: 8px 14px; border: 1px solid rgba(255,255,255,0.08); }"
        )
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(2)
        t = muted_label(title)
        val = QLabel(value)
        val.setObjectName("sectionTitle")
        val.setStyleSheet("font-size: 16px;")
        v.addWidget(t)
        v.addWidget(val)
        box._value_label = val  # type: ignore[attr-defined]
        return box

    def set_stats(
        self,
        *,
        planned_min: int,
        actual_min: int,
        block_count: int,
        segment_count: int,
    ) -> None:
        self._planned._value_label.setText(_fmt_minutes(planned_min))  # type: ignore[attr-defined]
        self._actual._value_label.setText(  # type: ignore[attr-defined]
            f"{_fmt_minutes(actual_min)} · {segment_count} seg"
        )
        self._blocks._value_label.setText(str(block_count))  # type: ignore[attr-defined]


class DayGrid2DWidget(QWidget):
    """Hour rows; X = minutes 0–60; actual top band, plan bottom band."""

    plan_block_clicked = Signal(dict)
    actual_segment_clicked = Signal(dict, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day = date.today()
        self._hour_lo = 6
        self._hour_hi = 22
        self._plan_segs: dict[int, list[dict[str, Any]]] = {h: [] for h in range(24)}
        self._hour_slices: dict[int, dict[str, Any]] = {}
        self._blocks_by_id: dict[int, dict[str, Any]] = {}
        self._hits: list[_GridHit] = []
        self._hover: _GridHit | None = None
        self.setMinimumWidth(560)
        self.setMouseTracking(True)

    def visible_hour_range(self) -> tuple[int, int]:
        return self._hour_lo, self._hour_hi

    def content_height(self) -> int:
        n = self._hour_hi - self._hour_lo + 1
        return AXIS_H + n * ROW_H + 8

    def set_data(
        self,
        day: date,
        plan_segs: list[dict[str, Any]],
        hour_slices: list[dict[str, Any]],
        *,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        self._day = day
        self._plan_segs = segs_by_hour(plan_segs)
        self._blocks_by_id = {int(b["id"]): b for b in (blocks or []) if b.get("id") is not None}
        day_k = day.isoformat()
        self._hour_slices = {}
        for sl in hour_slices or []:
            if str(sl.get("date") or "") == day_k:
                self._hour_slices[int(sl.get("hour") or 0)] = sl
        self._hour_lo, self._hour_hi = _visible_hour_range(self._plan_segs, self._hour_slices)
        self.setMinimumHeight(self.content_height())
        self._rebuild_hits()
        self.update()

    def _grid_w(self) -> int:
        return max(280, self.width() - LEFT_GUTTER - 16)

    def _row_geometry(self, hour: int) -> tuple[int, int, int, int, int, int]:
        idx = hour - self._hour_lo
        y = AXIS_H + idx * ROW_H
        row_top = y + 4
        row_h = ROW_H - 8
        divider = row_top + int(row_h * 0.42)
        actual_h = max(MIN_ACTUAL_H, divider - row_top - 2)
        plan_h = max(MIN_PLAN_H, row_top + row_h - divider - 2)
        actual_y = row_top + 1
        plan_y = divider + 2
        return y, row_h, plan_y, plan_h, actual_y, actual_h

    def _segment_tooltip(self, seg: dict, hour: int, kind: str) -> str:
        sm = int(seg.get("start_min") or 0)
        em = int(seg.get("end_min") or sm + 5)
        if kind == "plan":
            title = str(seg.get("title") or "Plan block")
            cat = str(seg.get("category") or "")
            return f"{title}\n{hour:02d}:{sm:02d}–{hour:02d}:{em:02d}\n{cat}"
        label = str(seg.get("app_or_label") or seg.get("category") or "Activity")
        mins = max(1, em - sm)
        return f"{label}\n{hour:02d}:{sm:02d}–{hour:02d}:{em:02d} · {mins}m"

    def _rebuild_hits(self) -> None:
        self._hits.clear()
        grid_w = self._grid_w()
        for hour in range(self._hour_lo, self._hour_hi + 1):
            _y, _rh, plan_y, plan_h, actual_y, actual_h = self._row_geometry(hour)
            sl = self._hour_slices.get(hour) or {}
            segments = [s for s in (sl.get("segments") or []) if isinstance(s, dict)]
            lane_count = max(1, int(sl.get("lane_count") or 1))
            lane_h = max(MIN_ACTUAL_H, actual_h // min(lane_count, MAX_ACTUAL_LANES))

            for i, seg in enumerate(segments[:MAX_ACTUAL_LANES]):
                sm = int(seg.get("start_min") or 0)
                em = int(seg.get("end_min") or sm + 5)
                lane = int(seg.get("lane_index") or i)
                x1 = LEFT_GUTTER + int((sm / 60.0) * grid_w)
                x2 = LEFT_GUTTER + int((em / 60.0) * grid_w)
                bw = max(MIN_PLAN_W, x2 - x1)
                ay = actual_y + min(lane, MAX_ACTUAL_LANES - 1) * lane_h
                rect = QRect(x1, ay, bw, max(7, lane_h - 2))
                tip = self._segment_tooltip(seg, hour, "actual")
                self._hits.append(_GridHit(rect, "actual", seg, hour, tip))

            for seg in self._plan_segs.get(hour) or []:
                sm = int(seg.get("start_min") or 0)
                em = int(seg.get("end_min") or sm + 15)
                x1 = LEFT_GUTTER + int((sm / 60.0) * grid_w)
                x2 = LEFT_GUTTER + int((em / 60.0) * grid_w)
                bw = max(MIN_PLAN_W, x2 - x1)
                rect = QRect(x1, plan_y, bw, plan_h)
                bid = int(seg.get("block_id") or 0)
                block = self._blocks_by_id.get(bid) or {
                    "id": bid,
                    "title": seg.get("title"),
                    "category": seg.get("category"),
                    "status": seg.get("status"),
                    "start_at": seg.get("start_at"),
                    "end_at": seg.get("end_at"),
                }
                tip = self._segment_tooltip({**seg, **block}, hour, "plan")
                self._hits.append(_GridHit(rect, "plan", block, hour, tip))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rebuild_hits()

    def _hit_at(self, pos: QPoint) -> _GridHit | None:
        plan_hits = [h for h in self._hits if h.kind == "plan" and h.rect.contains(pos)]
        if plan_hits:
            return plan_hits[-1]
        for h in self._hits:
            if h.kind == "actual" and h.rect.contains(pos):
                return h
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        hit = self._hit_at(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.setCursor(
                QCursor(Qt.CursorShape.PointingHandCursor)
                if hit
                else QCursor(Qt.CursorShape.ArrowCursor)
            )
            self.setToolTip(hit.tooltip if hit else "")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.setToolTip("")
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_at(event.position().toPoint())
            if hit:
                if hit.kind == "plan":
                    self.plan_block_clicked.emit(hit.payload)
                else:
                    self.actual_segment_clicked.emit(hit.payload, hit.hour)
                return
        super().mousePressEvent(event)

    def _draw_now_line(self, p: QPainter, grid_w: int) -> None:
        if self._day != date.today():
            return
        now = datetime.now()
        if not (self._hour_lo <= now.hour <= self._hour_hi):
            return
        _y, row_h, *_rest = self._row_geometry(now.hour)
        x = LEFT_GUTTER + int((now.minute / 60.0) * grid_w)
        p.setPen(QPen(QColor("#f87171"), 2))
        p.drawLine(x, _y + 2, x, _y + row_h - 2)
        p.setPen(QColor("#fca5a5"))
        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        p.drawText(x + 3, _y + 12, "now")

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        grid_w = self._grid_w()

        p.fillRect(self.rect(), QColor("#0b1220"))

        # Sticky-style axis
        p.fillRect(0, 0, self.width(), AXIS_H, QColor("#1e293b"))
        p.setPen(QColor(100, 116, 139))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(LEFT_GUTTER, 12, "Actual ↑")
        p.drawText(LEFT_GUTTER, 24, "Plan ↓")
        for m in (0, 15, 30, 45):
            x = LEFT_GUTTER + int((m / 60.0) * grid_w)
            p.setPen(QColor(71, 85, 105))
            p.drawLine(x, AXIS_H - 10, x, AXIS_H - 2)
            if m < 60:
                p.drawText(x - 8, AXIS_H - 12, f":{m:02d}")

        for hour in range(self._hour_lo, self._hour_hi + 1):
            y, row_h, plan_y, plan_h, actual_y, actual_h = self._row_geometry(hour)
            idx = hour - self._hour_lo

            if idx % 2 == 0:
                p.fillRect(LEFT_GUTTER, y, grid_w, ROW_H, QColor(15, 23, 42, 100))

            p.setPen(QPen(QColor(51, 65, 85)))
            p.drawLine(LEFT_GUTTER, y + ROW_H, LEFT_GUTTER + grid_w, y + ROW_H)

            # Band tint
            divider = actual_y + actual_h + 2
            p.fillRect(LEFT_GUTTER + 1, actual_y, grid_w - 2, actual_h + 2, QColor(56, 189, 248, 18))
            p.fillRect(LEFT_GUTTER + 1, plan_y, grid_w - 2, plan_h, QColor(217, 119, 6, 22))

            p.setPen(QColor(148, 163, 184))
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            p.drawText(8, y + 26, f"{hour:02d}")
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QColor(100, 116, 139))
            p.drawText(8, y + 38, "00")

            for m in (15, 30, 45):
                x = LEFT_GUTTER + int((m / 60.0) * grid_w)
                p.setPen(QColor(51, 65, 85, 80))
                p.drawLine(x, y + 3, x, y + ROW_H - 3)

            sl = self._hour_slices.get(hour) or {}
            segments = [s for s in (sl.get("segments") or []) if isinstance(s, dict)]
            lane_count = max(1, int(sl.get("lane_count") or 1))
            lane_h = max(MIN_ACTUAL_H, actual_h // min(lane_count, MAX_ACTUAL_LANES))
            hidden = max(0, len(segments) - MAX_ACTUAL_LANES)

            for i, seg in enumerate(segments[:MAX_ACTUAL_LANES]):
                sm = int(seg.get("start_min") or 0)
                em = int(seg.get("end_min") or sm + 5)
                lane = int(seg.get("lane_index") or i)
                x1 = LEFT_GUTTER + int((sm / 60.0) * grid_w)
                x2 = LEFT_GUTTER + int((em / 60.0) * grid_w)
                bw = max(MIN_PLAN_W, x2 - x1)
                bar_h = max(9, lane_h - 2)
                ay = actual_y + min(lane, MAX_ACTUAL_LANES - 1) * lane_h
                col = QColor(_ACTUAL_PALETTE[lane % len(_ACTUAL_PALETTE)])
                col.setAlpha(220)
                p.setBrush(col)
                p.setPen(QPen(QColor(255, 255, 255, 55), 1))
                bar_rect = QRect(x1, ay, bw, bar_h)
                p.drawRoundedRect(bar_rect, 4, 4)
                label = _short_label(str(seg.get("app_or_label") or seg.get("category") or ""))
                if label:
                    _draw_bar_text(
                        p,
                        bar_rect,
                        title=label,
                        light_on_dark=False,
                        two_line=bw >= 100 and bar_h >= 18,
                        subtitle=_format_seg_time(hour, sm, em) if bw >= 100 else "",
                    )

            if hidden > 0:
                p.setPen(QColor("#94a3b8"))
                p.setFont(QFont("Segoe UI", 8))
                p.drawText(LEFT_GUTTER + grid_w - 36, actual_y + 12, f"+{hidden}")

            for seg in self._plan_segs.get(hour) or []:
                sm = int(seg.get("start_min") or 0)
                em = int(seg.get("end_min") or sm + 15)
                x1 = LEFT_GUTTER + int((sm / 60.0) * grid_w)
                x2 = LEFT_GUTTER + int((em / 60.0) * grid_w)
                bw = max(MIN_PLAN_W, x2 - x1)
                color = _cat_color(str(seg.get("category") or ""))
                status = str(seg.get("status") or "")
                if status == "done":
                    color = QColor("#166534")
                elif seg.get("is_draft"):
                    color = QColor(color.red(), color.green(), color.blue(), 150)

                bid = int(seg.get("block_id") or 0)
                is_hover = (
                    self._hover
                    and self._hover.kind == "plan"
                    and int(self._hover.payload.get("id") or 0) == bid
                )
                p.setPen(QPen(QColor("#fbbf24" if is_hover else "#ffffff"), 2 if is_hover else 1))
                p.setBrush(color)
                bar_rect = QRect(x1, plan_y, bw, plan_h)
                p.drawRoundedRect(bar_rect, 6, 6)

                title = str(seg.get("title") or "").strip()
                if title:
                    time_line = _format_seg_time(hour, sm, em)
                    wide = bw >= 100 and plan_h >= 28
                    _draw_bar_text(
                        p,
                        bar_rect,
                        title=title,
                        subtitle=time_line,
                        light_on_dark=True,
                        two_line=wide,
                    )

        self._draw_now_line(p, grid_w)
        p.end()


class DayGrid2DPanel(QWidget):
    plan_block_clicked = Signal(dict)
    actual_segment_clicked = Signal(dict, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self._legend = CalendarLegend()
        lay.addWidget(self._legend)
        self._summary = CalendarSummaryBar()
        lay.addWidget(self._summary)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._grid = DayGrid2DWidget()
        self._grid.plan_block_clicked.connect(self.plan_block_clicked.emit)
        self._grid.actual_segment_clicked.connect(self.actual_segment_clicked.emit)
        self._scroll.setWidget(self._grid)
        lay.addWidget(self._scroll, stretch=1)

    def grid(self) -> DayGrid2DWidget:
        return self._grid

    def set_data(
        self,
        day: date,
        plan_segs: list,
        hour_slices: list,
        *,
        blocks: list | None = None,
    ) -> None:
        self._grid.set_data(day, plan_segs, hour_slices, blocks=blocks)
        planned_min = sum(int(b.get("planned_minutes") or 0) for b in (blocks or []))
        actual_min = 0
        n_actual = 0
        day_k = day.isoformat()
        for sl in hour_slices or []:
            if str(sl.get("date") or "") != day_k:
                continue
            for seg in sl.get("segments") or []:
                if not isinstance(seg, dict):
                    continue
                n_actual += 1
                sm = int(seg.get("start_min") or 0)
                em = int(seg.get("end_min") or sm + 5)
                actual_min += max(0, em - sm)
        self._summary.set_stats(
            planned_min=planned_min,
            actual_min=actual_min,
            block_count=len(blocks or []),
            segment_count=n_actual,
        )
        lo, hi = self._grid.visible_hour_range()
        scroll_to = 0
        if day == date.today():
            now_h = datetime.now().hour
            if lo <= now_h <= hi:
                scroll_to = max(0, (now_h - lo - 1) * ROW_H)
        self._scroll.verticalScrollBar().setValue(scroll_to)
