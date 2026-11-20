"""Janela de configurações."""

from __future__ import annotations

import sys
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .brand import MUTED, SIGNATURE
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

        self.recording_box = self._recording_section(settings) if sys.platform == "win32" else None

        buttons = QDialogButtonBox(self)
        buttons.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        signature = QLabel(SIGNATURE, self)
        signature.setAlignment(Qt.AlignmentFlag.AlignCenter)
        signature.setStyleSheet(f"color: {MUTED};")

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        if self.recording_box is not None:
            lay.addWidget(self.recording_box)
        lay.addWidget(buttons)
        lay.addWidget(signature)

    def _recording_section(self, settings: Settings) -> QGroupBox:
        box = QGroupBox("Gravação", self)
        form = QFormLayout(box)
        row = QHBoxLayout()
        self.video_dir = QLineEdit(settings.video_dir, box)
        browse = QPushButton("Escolher…", box)
        browse.clicked.connect(self._browse_videos)
        row.addWidget(self.video_dir, 1)
        row.addWidget(browse)
        form.addRow("Pasta dos vídeos", row)

        self.rec_resolution = QComboBox(box)
        for key, label in (("original", "Original"), ("1080", "1080p"), ("720", "720p"), ("480", "480p")):
            self.rec_resolution.addItem(label, key)
        self.rec_resolution.setCurrentIndex(max(0, self.rec_resolution.findData(settings.rec_resolution)))
        form.addRow("Resolução", self.rec_resolution)

        self.rec_fps = QComboBox(box)
        for fps in (30, 15):
            self.rec_fps.addItem(f"{fps} por segundo", fps)
        self.rec_fps.setCurrentIndex(max(0, self.rec_fps.findData(settings.rec_fps)))
        form.addRow("Quadros", self.rec_fps)

        self.rec_quality = QComboBox(box)
        for key, label in (("alta", "Alta"), ("media", "Média"), ("leve", "Leve (arquivo menor)")):
            self.rec_quality.addItem(label, key)
        self.rec_quality.setCurrentIndex(max(0, self.rec_quality.findData(settings.rec_quality)))
        form.addRow("Qualidade", self.rec_quality)

        self.rec_compress = QCheckBox("Comprimir depois de gravar, como o HandBrake (x264)", box)
        self.rec_compress.setChecked(settings.rec_compress)
        form.addRow("", self.rec_compress)

        self.ptt_hotkey = HotkeyEdit(settings.ptt_hotkey, box)
        form.addRow("Tecla de apertar para falar", self.ptt_hotkey)

        self.rec_countdown = QCheckBox("Contagem de 3 segundos antes de gravar", box)
        self.rec_countdown.setChecked(settings.rec_countdown)
        form.addRow("", self.rec_countdown)
        return box

    def _browse_videos(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta dos vídeos", self.video_dir.text())
        if d:
            self.video_dir.setText(d)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta padrão", self.save_dir.text())
        if d:
            self.save_dir.setText(d)

    def current(self) -> Settings:
        s = replace(
            self._settings,
            hotkey=self.hotkey.value,
            autostart=self.autostart.isChecked(),
            save_dir=self.save_dir.text().strip() or self._settings.save_dir,
            image_format=self.image_format.currentText(),
        )
        if self.recording_box is not None:
            s = replace(
                s,
                video_dir=self.video_dir.text().strip() or self._settings.video_dir,
                rec_resolution=self.rec_resolution.currentData(),
                rec_fps=self.rec_fps.currentData(),
                rec_quality=self.rec_quality.currentData(),
                rec_compress=self.rec_compress.isChecked(),
                ptt_hotkey=self.ptt_hotkey.value,
                rec_countdown=self.rec_countdown.isChecked(),
            )
        return s

    def _save(self) -> None:
        self.saved.emit(self.current())
        self.accept()
