"""Liga bandeja, atalho, captura, editor e configurações."""

from __future__ import annotations

import logging
import sys
from dataclasses import replace

from PySide6.QtCore import QObject, QRect, QSize, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .autostart import set_autostart
from .editor import Editor
from .hotkey import GlobalHotkey, HotkeyError, is_wayland
from .ocr import get_engine
from .recording.controller import RecordingController
from .overlay import CaptureSession
from .settings import Settings, load_settings, save_settings, translate_hotkey_conflicts
from .settings_window import SettingsWindow, owned_fields
from .single_instance import SingleInstance
from .translate.google import GoogleTranslator
from .translate.grab import QtBackend, WinBackend, grab, mask_alt_menu
from .translate.window import TranslatorWindow
from .tray import Tray, app_icon

log = logging.getLogger(__name__)
# a janela manda só 5.000 ao Google; isto evita encher a caixa com uma área de transferência enorme
MAX_GRABBED_CHARS = 100_000
TRANSLATOR_FIELDS = ("translate_source", "translate_target", "translate_recent", "translate_size", "translate_pinned")


def _safe_grab(backend_factory, grab_selection: bool) -> tuple[str, str]:
    """Texto e origem; numa falha, devolve vazio para a janela abrir mesmo assim."""
    try:
        got = grab(backend_factory(), grab_selection)
        return got.text, got.source
    except Exception:  # noqa: BLE001
        log.exception("Falha ao pegar o texto para traduzir")
        return "", "none"


class App(QObject):
    # o pynput chama de outra thread; o sinal leva o pedido para a thread da interface
    _hotkey_pressed = Signal()
    _translate_pressed = Signal()
    _grabbed = Signal(str, str)  # texto, origem

    def __init__(self, qapp: QApplication, instance: SingleInstance):
        super().__init__()
        self.qapp = qapp
        qapp.setQuitOnLastWindowClosed(False)
        qapp.setWindowIcon(app_icon())
        self.settings: Settings = load_settings()
        self.session: CaptureSession | None = None
        self.settings_window: SettingsWindow | None = None
        self.hotkey: GlobalHotkey | None = None
        self.translate_hotkey: GlobalHotkey | None = None
        self.translator: GoogleTranslator | None = None
        self.translator_window: TranslatorWindow | None = None
        self._grabbing = False
        self._quitting = False
        # pool próprio para o quit esperar a thread de pegar texto
        self._grab_pool = QThreadPool(self)

        self.tray = Tray(self)
        self.tray.capture_requested.connect(self.capture)
        self.tray.translate_requested.connect(self._translate_from_tray)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.quit_requested.connect(self.quit)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.recorder = RecordingController(self.settings, self.tray, self._save_from_recording, parent=self)
        self.tray.stop_recording_requested.connect(self.recorder.stop)
        self.tray.messageClicked.connect(self.recorder.message_clicked)

        self._hotkey_pressed.connect(self.on_hotkey)
        self._start_hotkey()
        self._translate_pressed.connect(self.translate_shortcut)
        self._grabbed.connect(self._on_grabbed)
        self._start_translate_hotkey()
        self._apply_autostart()

        instance.message_received.connect(self.handle_message)

    # ---------- atalho e autostart ----------
    def _start_hotkey(self) -> None:
        if is_wayland():
            self.tray.set_hotkey_hint(None)
            return
        try:
            if self.hotkey is None:
                self.hotkey = GlobalHotkey(self.settings.hotkey, self._hotkey_pressed.emit)
                self.hotkey.start()
            else:
                self.hotkey.rebind(self.settings.hotkey)
            self.tray.set_hotkey_hint(self.settings.hotkey)
        except HotkeyError as e:
            self.hotkey = None
            self.tray.notify("Parzprint", f"Atalho indisponível: {e}")

    def _on_translate_hotkey(self) -> None:
        # na thread do atalho: o Alt tem que ser mascarado antes de a pessoa soltar
        try:
            mask_alt_menu()
        except Exception:  # noqa: BLE001
            log.exception("Falha ao mascarar o Alt do atalho do tradutor")
        finally:
            self._translate_pressed.emit()

    def _start_translate_hotkey(self) -> None:
        if is_wayland():
            return
        if translate_hotkey_conflicts(self.settings):
            if self.translate_hotkey is not None:
                self.translate_hotkey.stop()
                self.translate_hotkey = None
            self.tray.notify("Parzprint", "O atalho do tradutor é igual a outro atalho. Troque em Configurações.")
            return
        try:
            if self.translate_hotkey is None:
                self.translate_hotkey = GlobalHotkey(self.settings.translate_hotkey, self._on_translate_hotkey)
                self.translate_hotkey.start()
            else:
                self.translate_hotkey.rebind(self.settings.translate_hotkey)
        except HotkeyError as e:
            self.translate_hotkey = None
            self.tray.notify("Parzprint", f"Atalho do tradutor indisponível: {e}")

    def _apply_autostart(self) -> None:
        try:
            set_autostart(self.settings.autostart)
        except OSError as e:
            self.tray.notify("Parzprint", f"Não foi possível configurar o início automático: {e}")

    # ---------- ações ----------
    def handle_message(self, message: str) -> None:
        if message == "capture":
            self.on_hotkey()
        elif message == "settings":
            self.open_settings()
        elif message == "translate":
            self.translate_shortcut()
        else:
            self.tray.notify("Parzprint", "O Parzprint já está aberto na bandeja.")

    def on_hotkey(self) -> None:
        """Durante uma gravação, o atalho de captura para a gravação."""
        if self.recorder.active:
            self.recorder.stop()
        else:
            self.capture()

    # ---------- tradutor ----------
    def translate_shortcut(self) -> None:
        if self._grabbing:
            return
        self._grabbing = True
        grab_selection = self.settings.translate_grab_selection
        if sys.platform == "win32":
            # o Ctrl+C e a espera pela área de transferência não podem travar a interface
            self._grab_pool.start(lambda: self._grabbed.emit(*_safe_grab(WinBackend, grab_selection)))
        else:
            self._on_grabbed(*_safe_grab(QtBackend, grab_selection))

    def _on_grabbed(self, text: str, source: str) -> None:
        self._grabbing = False
        if self._quitting:
            return
        self.open_translator(text[:MAX_GRABBED_CHARS], self._cursor_anchor(), auto=(source == "selection"))

    def _translate_from_tray(self) -> None:
        self.open_translator("", self._cursor_anchor(), auto=False)

    @staticmethod
    def _cursor_anchor() -> QRect:
        return QRect(QCursor.pos(), QSize(1, 1))

    def open_translator(self, text: str, anchor: QRect, auto: bool) -> None:
        if self.translator_window is None:
            self.translator = GoogleTranslator(parent=self)
            self.translator_window = TranslatorWindow(self.translator, self.settings, self._save_from_translator)
        self.translator_window.open(text, anchor, auto)

    def _save_from_translator(self, settings: Settings) -> None:
        # a janela pode ter uma cópia antiga: só os campos dela valem
        merged = replace(self.settings, **{name: getattr(settings, name) for name in TRANSLATOR_FIELDS})
        self.recorder.settings = merged
        self._save_from_recording(merged)

    def _save_from_recording(self, settings: Settings) -> None:
        self.settings = settings
        if self.translator_window is not None:
            self.translator_window.settings = settings
        try:
            save_settings(settings)
        except OSError as e:
            self.tray.notify("Parzprint", f"Não foi possível salvar as configurações: {e}")

    def capture(self) -> None:
        if self.session is not None or self.recorder.active:
            return
        session = CaptureSession(parent=self)
        session.region_ready.connect(self._on_region)
        session.failed.connect(lambda msg: self.tray.notify("Parzprint", f"Falha na captura: {msg}"))
        session.finished.connect(self._on_session_finished)
        self.session = session
        # pequena espera para o menu da bandeja sumir antes da foto
        QTimer.singleShot(150, session.start)

    def _on_region(self, overlay, _rect) -> None:
        editor = Editor(overlay, self.settings, engine_provider=lambda: get_engine(self.settings.ocr_engine))
        editor.record_requested.connect(self.recorder.start)
        editor.translate_requested.connect(lambda text, area: self.open_translator(text, area, auto=True))

    def _on_session_finished(self) -> None:
        if self.session is not None:
            self.session.deleteLater()
        self.session = None

    def open_settings(self) -> None:
        if self.settings_window is not None:
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        win = SettingsWindow(self.settings)
        win.saved.connect(self.apply_settings)
        win.finished.connect(self._on_settings_closed)
        self.settings_window = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _on_settings_closed(self, _result) -> None:
        if self.settings_window is not None:
            self.settings_window.deleteLater()
        self.settings_window = None

    def apply_settings(self, new: Settings) -> None:
        old = self.settings
        # a janela de configurações não é modal: idiomas e tamanho do tradutor podem ter mudado depois que ela abriu
        new = replace(old, **{name: getattr(new, name) for name in owned_fields()})
        self.settings = new
        self.recorder.settings = new
        try:
            save_settings(new)
        except OSError as e:
            self.tray.notify("Parzprint", f"Não foi possível salvar as configurações: {e}")
        if self.translator_window is not None:
            self.translator_window.settings = new
        if new.hotkey != old.hotkey:
            self._start_hotkey()
        if new.translate_hotkey != old.translate_hotkey:
            self._start_translate_hotkey()
        if new.autostart != old.autostart:
            self._apply_autostart()

    def quit(self) -> None:
        self.recorder.shutdown()
        from .recording.compress import running_workers

        for worker in running_workers():
            worker.abort()
        if self.hotkey is not None:
            self.hotkey.stop()
        if self.translate_hotkey is not None:
            self.translate_hotkey.stop()
        self._quitting = True
        self._grab_pool.waitForDone(1000)
        if self.translator_window is not None:
            self.translator_window.close()
        if self.translator is not None:
            self.translator.shutdown()
        if self.session is not None:
            self.session.close()
        self.tray.hide()
        self.qapp.quit()
