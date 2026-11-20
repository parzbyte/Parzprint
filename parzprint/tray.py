"""Ícone na bandeja do sistema."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .brand import SIGNATURE

ASSETS = Path(__file__).resolve().parent / "assets"


def app_icon() -> QIcon:
    return QIcon(str(ASSETS / "icon.png"))


class Tray(QSystemTrayIcon):
    capture_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    stop_recording_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(app_icon(), parent)
        self.setToolTip(SIGNATURE)
        menu = QMenu()
        self._stop_action = menu.addAction("Parar gravação", self.stop_recording_requested.emit)
        self._stop_action.setVisible(False)
        menu.addAction("Capturar", self.capture_requested.emit)
        menu.addAction("Configurações", self.settings_requested.emit)
        menu.addSeparator()
        menu.addAction("Sair", self.quit_requested.emit)
        self._menu = menu  # mantém a referência viva
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def set_hotkey_hint(self, hotkey: str | None) -> None:
        self.setToolTip(f"{SIGNATURE} ({hotkey})" if hotkey else SIGNATURE)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.capture_requested.emit()

    def set_recording(self, on: bool) -> None:
        self._stop_action.setVisible(on)

    def notify(self, title: str, text: str) -> None:
        self.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 4000)
