"""Bible tab — morning chapter + afternoon Proverbs/Psalms + evening praise."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


def _chapter_html(chapter: dict[str, Any]) -> str:
    name = html.escape(str(chapter.get("name") or ""))
    ch = int(chapter.get("chapter") or 1)
    version = html.escape(str(chapter.get("version_name") or chapter.get("version") or "WEB"))
    parts = [
        f'<div style="color:#94a3b8;font-size:12px;margin-bottom:8px;">{version}</div>',
        f'<h2 style="color:#ecfdf5;margin:0 0 12px 0;">{name} {ch}</h2>',
    ]
    for v in chapter.get("verses") or []:
        num = int(v.get("number") or 0)
        text = html.escape(str(v.get("text") or ""))
        parts.append(
            f'<p style="margin:0 0 10px 0;line-height:1.55;">'
            f'<sup style="color:#34d399;font-weight:600;margin-right:6px;">{num}</sup>'
            f'<span style="color:#e2e8f0;">{text}</span></p>'
        )
    return "".join(parts)


def _prayer_html(title: str, body: str) -> str:
    lines = "".join(
        f'<p style="margin:0 0 8px 0;color:#e2e8f0;line-height:1.5;">{html.escape(line)}</p>'
        for line in str(body or "").splitlines()
        if line.strip()
    )
    return (
        f'<h3 style="color:#a7f3d0;margin:0 0 8px 0;font-size:14px;">{html.escape(title)}</h3>'
        f"{lines}"
    )


def _note_html(note: str) -> str:
    return (
        f'<p style="color:#94a3b8;font-size:12px;margin:0 0 12px 0;line-height:1.45;">'
        f"{html.escape(note)}</p>"
    )


class _DevotionPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._info = muted_label("…")
        lay.addWidget(self._info)
        panel = GlossPanel()
        self._reader = QTextBrowser()
        self._reader.setOpenExternalLinks(True)
        self._reader.setStyleSheet(
            "QTextBrowser { background: rgba(15,23,42,0.5); border: none; padding: 4px; }"
        )
        panel.body_layout().addWidget(self._reader)
        lay.addWidget(panel, stretch=1)
        row = QHBoxLayout()
        self._btn = primary_button("Mark done")
        row.addWidget(self._btn)
        row.addStretch(1)
        lay.addLayout(row)


class BibleTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 30_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self._rendered: dict[str, str] = {}
        lay = QVBoxLayout(self)

        lay.addWidget(
            SectionHeader(
                "Daily devotion",
                "Morning (Lord's Prayer + chapter) · Afternoon Proverbs · Evening Psalms + worship.",
            )
        )

        self._tabs = QTabWidget()
        self._morning = _DevotionPage()
        self._afternoon = _DevotionPage()
        self._evening = _DevotionPage()
        self._tabs.addTab(self._morning, "Morning")
        self._tabs.addTab(self._afternoon, "Afternoon")
        self._tabs.addTab(self._evening, "Evening")
        lay.addWidget(self._tabs, stretch=1)

        self._morning._btn.setText("Mark morning chapter done")
        self._morning._btn.clicked.connect(self._mark_morning)
        self._afternoon._btn.setText("Mark afternoon reading done")
        self._afternoon._btn.clicked.connect(self._mark_afternoon)
        self._evening._btn.setText("Mark evening praise done")
        self._evening._btn.clicked.connect(self._mark_evening)

        self._init_visible_poll()

    def refresh(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            for page in (self._morning, self._afternoon, self._evening):
                page._info.setText("Waiting for tracker user…")
            return
        try:
            self._refresh_morning(uid)
            self._refresh_afternoon(uid)
            self._refresh_evening(uid)
        except Exception as exc:  # noqa: BLE001
            self._morning._info.setText(f"Load failed: {exc}")

    def _refresh_morning(self, uid: int) -> None:
        from backend.bible import store as bible_store
        from backend.bible.structured import read_chapter

        devo = bible_store.devotion_summary(uid)
        morning = devo.get("morning") or {}
        today = bible_store.resolve_today_chapter(uid)
        chapters = (bible_store.summary(uid).get("chapters_completed_today") or [])
        done = bool(today.get("done")) or today.get("key") in chapters
        book = str(today.get("book") or "")
        chapter_n = int(today.get("chapter") or 1)
        label = str(today.get("label") or f"{book} {chapter_n}")
        chapter_key = str(today.get("key") or f"{book}|{chapter_n}")

        self._morning._info.setText(f"Today's chapter: {label} · Done: {'yes' if done else 'no'}")
        cache_key = f"m:{chapter_key}"
        if cache_key != self._rendered.get("morning"):
            parts = [
                _note_html(str(morning.get("note") or "")),
                _prayer_html("The Lord's Prayer", str(morning.get("lords_prayer") or "")),
                "<hr style='border-color:rgba(255,255,255,0.08);margin:14px 0;'/>",
            ]
            try:
                chapter = read_chapter("web", book, chapter_n)
                parts.append(_chapter_html(chapter))
            except Exception as exc:  # noqa: BLE001
                parts.append(f'<p style="color:#fca5a5;">{html.escape(str(exc))}</p>')
            self._morning._reader.setHtml("".join(parts))
            self._rendered["morning"] = cache_key
        self._morning._btn.setEnabled(not done)
        self._tabs.setTabText(0, "Morning ✓" if done else "Morning")

    def _refresh_afternoon(self, uid: int) -> None:
        from backend.bible import store as bible_store
        from backend.bible.structured import read_chapter

        devo = bible_store.devotion_summary(uid)
        aft = devo.get("afternoon") or {}
        done = bool(aft.get("done"))
        book = str(aft.get("book") or "Proverbs")
        chapter_n = int(aft.get("chapter") or 1)
        label = str(aft.get("label") or f"{book} {chapter_n}")
        cache_key = f"a:{aft.get('key')}"
        self._afternoon._info.setText(f"Afternoon: {label} · Done: {'yes' if done else 'no'}")
        if cache_key != self._rendered.get("afternoon"):
            parts = [
                _note_html(str(aft.get("note") or "")),
                _prayer_html("Prayer — wisdom, guidance, healing, work & life", str(aft.get("prayer") or "")),
                "<hr style='border-color:rgba(255,255,255,0.08);margin:14px 0;'/>",
            ]
            try:
                chapter = read_chapter("web", book, chapter_n)
                parts.append(_chapter_html(chapter))
            except Exception as exc:  # noqa: BLE001
                parts.append(f'<p style="color:#fca5a5;">{html.escape(str(exc))}</p>')
            self._afternoon._reader.setHtml("".join(parts))
            self._rendered["afternoon"] = cache_key
        self._afternoon._btn.setEnabled(not done)
        self._tabs.setTabText(1, "Afternoon ✓" if done else "Afternoon")

    def _refresh_evening(self, uid: int) -> None:
        from backend.bible import store as bible_store
        from backend.bible.structured import read_chapter

        devo = bible_store.devotion_summary(uid)
        eve = devo.get("evening") or {}
        done = bool(eve.get("done"))
        book = str(eve.get("book") or "Psalms")
        chapter_n = int(eve.get("chapter") or 1)
        label = str(eve.get("label") or f"{book} {chapter_n}")
        worship = str(eve.get("worship_title") or "Worship hymn")
        cache_key = f"e:{eve.get('key')}|{eve.get('hymn_id')}"
        self._evening._info.setText(
            f"Evening: {label} + {worship} · Done: {'yes' if done else 'no'}"
        )
        if cache_key != self._rendered.get("evening"):
            parts = [
                _note_html(str(eve.get("note") or "")),
            ]
            try:
                chapter = read_chapter("web", book, chapter_n)
                parts.append(_chapter_html(chapter))
            except Exception as exc:  # noqa: BLE001
                parts.append(f'<p style="color:#fca5a5;">{html.escape(str(exc))}</p>')
            parts.append("<hr style='border-color:rgba(255,255,255,0.08);margin:14px 0;'/>")
            parts.append(
                _prayer_html(
                    f"Worship — {worship}",
                    f"{eve.get('worship_opening', '')}\n\nTheme: {eve.get('worship_theme', 'praise')}",
                )
            )
            notes = str(eve.get("notes") or "").strip()
            if notes:
                parts.append(
                    f'<h3 style="color:#cbd5e1;margin:16px 0 8px 0;font-size:13px;">Your notes</h3>'
                    f'<p style="color:#e2e8f0;white-space:pre-wrap;">{html.escape(notes)}</p>'
                )
            self._evening._reader.setHtml("".join(parts))
            self._rendered["evening"] = cache_key
        self._evening._btn.setEnabled(not done)
        self._tabs.setTabText(2, "Evening ✓" if done else "Evening")

    def _mark_morning(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            return
        try:
            from backend.bible import store as bible_store
            from backend.planner import morning_rewards as morning_rewards_store

            today = bible_store.resolve_today_chapter(uid)
            bible_store.tick_chapter(
                uid,
                book=str(today.get("book") or ""),
                chapter=int(today.get("chapter") or 1),
                done=True,
            )
            self._rendered.pop("morning", None)
            try:
                morning_rewards_store.maybe_grant_bible(uid)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.refresh()
            QMessageBox.information(self, "Morning Bible", "Chapter marked done. Next: Plan tab.")
            go_tab("Plan")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Bible", str(exc))

    def _mark_afternoon(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            return
        try:
            from backend.bible import store as bible_store

            bible_store.mark_devotion_done(uid, "afternoon", done=True)
            self._rendered.pop("afternoon", None)
            self.refresh()
            QMessageBox.information(self, "Afternoon devotion", "Afternoon reading logged.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Bible", str(exc))

    def _mark_evening(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            return
        try:
            from backend.bible import store as bible_store

            bible_store.mark_devotion_done(uid, "evening", done=True)
            self._rendered.pop("evening", None)
            self.refresh()
            QMessageBox.information(self, "Evening praise", "Evening hymn praise logged.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Bible", str(exc))
