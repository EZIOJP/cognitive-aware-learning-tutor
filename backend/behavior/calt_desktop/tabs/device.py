"""Device block tab — hosts-file status (Admin apply via bat)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DeviceTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Device-wide hosts block"))
        self._status = QLabel("…")
        self._status.setWordWrap(True)
        lay.addWidget(self._status)
        self._porn = QCheckBox("Block porn domains")
        self._watch = QCheckBox("Block YouTube / watch")
        self._social = QCheckBox("Block social")
        for c in (self._porn, self._watch, self._social):
            lay.addWidget(c)

        row = QHBoxLayout()
        btn_reload = QPushButton("Refresh status")
        btn_reload.clicked.connect(self.reload)
        btn_save = QPushButton("Save settings")
        btn_save.clicked.connect(self.save_settings)
        row.addWidget(btn_reload)
        row.addWidget(btn_save)
        lay.addLayout(row)

        tip = QLabel(
            "Applying hosts requires Admin:\n"
            "  scripts\\device_block_apply.bat\n"
            "  scripts\\device_block_remove.bat"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)
        self.reload()

    def reload(self) -> None:
        from backend.behavior import device_block as db

        st = db.status()
        settings = db.load_settings()
        self._porn.setChecked(bool(settings.get("block_porn", True)))
        self._watch.setChecked(bool(settings.get("block_watch", True)))
        self._social.setChecked(bool(settings.get("block_social", False)))
        active = st.get("active")
        count = st.get("managed_host_entries") or st.get("configured_domain_count") or "?"
        self._status.setText(
            f"Hosts section active: {active}\nManaged entries: {count}\n"
            f"Settings enabled flag: {settings.get('enabled')}\n"
            f"Needs sync: {st.get('needs_sync')}"
        )

    def save_settings(self) -> None:
        from backend.behavior import device_block as db

        try:
            data = db.load_settings()
            data["block_porn"] = self._porn.isChecked()
            data["block_watch"] = self._watch.isChecked()
            data["block_social"] = self._social.isChecked()
            db.save_settings(data)
            self.reload()
            QMessageBox.information(
                self,
                "Device",
                "Settings saved. Run device_block_apply.bat as Admin to write hosts.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Device", str(exc))
