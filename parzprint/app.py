"""Liga bandeja, atalho, captura, editor e configurações."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .autostart import set_autostart
from .editor import Editor
from .hotkey import GlobalHotkey, HotkeyError, is_wayland
from .ocr import get_engine
from .recording.controller import RecordingController
from .overlay import CaptureSession
from .settings import Settings, load_settings, save_settings
from .settings_window import SettingsWindow
from .single_instance import SingleInstance
from .tray import Tray, app_icon


class App(QObject):
    # o pynput chama de outra thread; o sinal leva o pedido para a thread da interface
    _hotkey_pressed = Signal()

    def __init__(self, qapp: QApplication, instance: SingleInstance):
        super().__init__()
        self.qapp = qapp
        qapp.setQuitOnLastWindowClosed(False)
        qapp.setWindowIcon(app_icon())
        self.settings: Settings = load_settings()
        self.session: CaptureSession | None = None
        self.settings_window: SettingsWindow | None = None
        self.hotkey: GlobalHotkey | None = None

        self.tray = Tray(self)
        self.tray.capture_requested.connect(self.capture)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.quit_requested.connect(self.quit)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.recorder = RecordingController(self.settings, self.tray, self._save_from_recording, parent=self)
        self.tray.stop_recording_requested.connect(self.recorder.stop)
        self.tray.messageClicked.connect(self.recorder.message_clicked)

        self._hotkey_pressed.connect(self.on_hotkey)
        self._start_hotkey()
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
        else:
            self.tray.notify("Parzprint", "O Parzprint já está aberto na bandeja.")

    def on_hotkey(self) -> None:
        """Durante uma gravação, o atalho de captura para a gravação."""
        if self.recorder.active:
            self.recorder.stop()
        else:
            self.capture()

    def _save_from_recording(self, settings: Settings) -> None:
        self.settings = settings
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
        self.settings = new
        self.recorder.settings = new
        try:
            save_settings(new)
        except OSError as e:
            self.tray.notify("Parzprint", f"Não foi possível salvar as configurações: {e}")
        if new.hotkey != old.hotkey:
            self._start_hotkey()
        if new.autostart != old.autostart:
            self._apply_autostart()

    def quit(self) -> None:
        self.recorder.shutdown()
        if self.hotkey is not None:
            self.hotkey.stop()
        if self.session is not None:
            self.session.close()
        self.tray.hide()
        self.qapp.quit()
