"""Ícone na bandeja do sistema."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

ASSETS = Path(__file__).resolve().parent / "assets"


def app_icon() -> QIcon:
    return QIcon(str(ASSETS / "icon.png"))


class Tray(QSystemTrayIcon):
    capture_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(app_icon(), parent)
        self.setToolTip("Parzprint")
        menu = QMenu()
        menu.addAction("Capturar", self.capture_requested.emit)
        menu.addAction("Configurações", self.settings_requested.emit)
        menu.addSeparator()
        menu.addAction("Sair", self.quit_requested.emit)
        self._menu = menu  # mantém a referência viva
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def set_hotkey_hint(self, hotkey: str | None) -> None:
        self.setToolTip(f"Parzprint ({hotkey})" if hotkey else "Parzprint")

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.capture_requested.emit()

    def notify(self, title: str, text: str) -> None:
        self.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 4000)
