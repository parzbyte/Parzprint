"""Janela de configurações."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .hotkey import HotkeyError, from_qt_key_event, is_wayland, to_pynput
from .settings import IMAGE_FORMATS, Settings
from .tray import app_icon

WAYLAND_HINT = (
    "Em Wayland o atalho global não é suportado. Cadastre nas configurações de teclado "
    "do sistema o comando: parzprint --capture"
)

_QT_MODS = (
    (Qt.KeyboardModifier.ControlModifier, "Ctrl"),
    (Qt.KeyboardModifier.ShiftModifier, "Shift"),
    (Qt.KeyboardModifier.AltModifier, "Alt"),
    (Qt.KeyboardModifier.MetaModifier, "Win"),
)
_MOD_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}


class HotkeyEdit(QLineEdit):
    """Campo que grava a combinação pressionada (ex.: Ctrl+Shift+S)."""

    def __init__(self, value: str, parent: QWidget | None = None):
        super().__init__(value, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Pressione a combinação…")
        self.value = value

    def keyPressEvent(self, e):
        if e.key() in _MOD_KEYS:
            return
        if e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            super().keyPressEvent(e)
            return
        from PySide6.QtGui import QKeySequence

        mods = {name for flag, name in _QT_MODS if e.modifiers() & flag}
        key = QKeySequence(e.key()).toString()
        combo = from_qt_key_event(mods, key)
        if combo is None:
            return
        try:
            to_pynput(combo)
        except HotkeyError:
            return
        self.value = combo
        self.setText(combo)


class SettingsWindow(QDialog):
    saved = Signal(object)  # Settings

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do Parzprint")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(460)
        self._settings = settings
        form = QFormLayout()

        self.hotkey = HotkeyEdit(settings.hotkey, self)
        form.addRow("Atalho de captura", self.hotkey)
        self.wayland_hint = QLabel(WAYLAND_HINT, self)
        self.wayland_hint.setWordWrap(True)
        self.wayland_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if is_wayland():
            self.hotkey.setEnabled(False)
            form.addRow("", self.wayland_hint)
        else:
            self.wayland_hint.hide()

        self.autostart = QCheckBox("Iniciar com o sistema", self)
        self.autostart.setChecked(settings.autostart)
        form.addRow("", self.autostart)

        row = QHBoxLayout()
        self.save_dir = QLineEdit(settings.save_dir, self)
        browse = QPushButton("Escolher…", self)
        browse.clicked.connect(self._browse)
        row.addWidget(self.save_dir, 1)
        row.addWidget(browse)
        form.addRow("Pasta padrão", row)

        self.image_format = QComboBox(self)
        self.image_format.addItems(list(IMAGE_FORMATS))
        self.image_format.setCurrentText(settings.image_format)
        form.addRow("Formato", self.image_format)

        buttons = QDialogButtonBox(self)
        buttons.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta padrão", self.save_dir.text())
        if d:
            self.save_dir.setText(d)

    def current(self) -> Settings:
        return replace(
            self._settings,
            hotkey=self.hotkey.value,
            autostart=self.autostart.isChecked(),
            save_dir=self.save_dir.text().strip() or self._settings.save_dir,
            image_format=self.image_format.currentText(),
        )

    def _save(self) -> None:
        self.saved.emit(self.current())
        self.accept()
