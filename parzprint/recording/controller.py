"""Liga a gravação ao app: janelas, apertar para falar, avisos na bandeja e saída segura."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from ..capture import Monitor
from ..settings import Settings

PTT_POLL_MS = 50


def open_in_explorer(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{path}"])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent)])


def _size_text(n: int) -> str:
    mb = n / (1024 * 1024)
    return f"{mb:.1f} MB".replace(".", ",") if mb >= 0.1 else f"{max(1, n // 1024)} KB"


def _screen_for(area: QRect):
    return QGuiApplication.screenAt(area.center()) or QGuiApplication.primaryScreen()


class RecordingController(QObject):
    _ptt_pressed = Signal()  # o atalho chega de outra thread; o sinal traz para a da interface

    def __init__(
        self, settings: Settings, tray, save_settings: Callable[[Settings], None], *,
        session_factory=None, layer_factory=None, frame_factory=None, bar_factory=None,
        hotkey_factory=None, key_down=None, opener: Callable[[Path], None] = open_in_explorer,
        screen_for: Callable[[QRect], object] = _screen_for, parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.tray = tray
        self._save_settings = save_settings
        self._session_factory = session_factory
        self._layer_factory = layer_factory
        self._frame_factory = frame_factory
        self._bar_factory = bar_factory
        self._hotkey_factory = hotkey_factory
        self._key_down = key_down
        self._opener = opener
        self._screen_for = screen_for
        self.session = None
        self.layer = self.frame = self.bar = None
        self._ptt = None
        self._last_saved: Path | None = None
        self._finishing: list = []  # sessões já paradas que ainda vão emitir "saved"
        self._ptt_timer = QTimer(self)
        self._ptt_timer.setInterval(PTT_POLL_MS)
        self._ptt_timer.timeout.connect(self._ptt_poll)
        self._ptt_pressed.connect(self._ptt_pressed_main)

    @property
    def active(self) -> bool:
        return self.session is not None and self.session.state in ("countdown", "recording", "paused")

    # ------------------------------------------------------------ início
    def start(self, monitor: Monitor, area: QRect, items: list) -> None:
        if self.active:
            return
        from .drawlayer import DrawLayer
        from .frame import AreaFrame
        from .recordbar import RecordBar
        from .session import RecordingSession

        screen = self._screen_for(area)
        session = (self._session_factory or RecordingSession)(self.settings, monitor, area, screen)
        self.session = session
        self.layer = (self._layer_factory or DrawLayer)(area, items, monitor.scale)
        self.frame = (self._frame_factory or AreaFrame)(area)
        self.bar = (self._bar_factory or RecordBar)(session, self.settings, self.layer)
        self.bar.settings_changed.connect(self._on_bar_settings)
        session.countdown_tick.connect(self.frame.show_count)
        session.state_changed.connect(self._on_state)
        session.saved.connect(self._on_saved)
        session.compressing.connect(lambda _p: self.tray.notify("Parzprint", "Comprimindo vídeo…"))
        session.failed.connect(lambda m: self.tray.notify("Parzprint", m))
        session.warning.connect(lambda m: self.tray.notify("Parzprint", m))
        self.layer.show()
        self.frame.show()
        self.bar.place(area)
        self.bar.show()
        self.tray.set_recording(True)
        session.begin(self.settings.rec_countdown)

    # ------------------------------------------------------------ estado
    def _on_state(self, state: str) -> None:
        if state == "recording":
            if self.frame is not None:
                self.frame.show_count(0)
            self._sync_ptt()
        elif state in ("stopping", "done", "cancelled"):
            self._end_ui()

    def _end_ui(self) -> None:
        self._stop_ptt()
        for w in (self.bar, self.frame, self.layer):
            if w is not None:
                w.close()
        self.bar = self.frame = self.layer = None
        if self.session is not None:
            self._finishing.append(self.session)
        self.session = None
        self.tray.set_recording(False)

    def stop(self) -> None:
        if self.session is not None:
            self.session.stop()

    def _on_bar_settings(self, settings: Settings) -> None:
        self._save_settings(settings)
        self._sync_ptt()

    # ------------------------------------------------------------ fim
    def _on_saved(self, path: Path, size: int) -> None:
        self._last_saved = Path(path)
        self.tray.notify("Parzprint", f"Vídeo salvo: {Path(path).name} ({_size_text(size)}). Clique para abrir a pasta.")
        self._finishing = [s for s in self._finishing if s is not self.sender()]

    def message_clicked(self) -> None:
        if self._last_saved is not None:
            self._opener(self._last_saved)

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Para a gravação e espera o arquivo ser fechado antes de o app sair."""
        session = self.session
        if session is None:
            return
        self.stop()
        t = QElapsedTimer()
        t.start()
        while session.state not in ("done", "cancelled") and t.elapsed() < timeout_ms:
            QCoreApplication.processEvents()

    # ------------------------------------------------------------ apertar para falar
    def _sync_ptt(self) -> None:
        if self.session is None or self.session.state not in ("recording", "paused"):
            return
        if self.settings.mic_mode == "ptt" and self._ptt is None:
            factory = self._hotkey_factory
            if factory is None:
                from ..hotkey import GlobalHotkey

                factory = GlobalHotkey
            hk = factory(self.settings.ptt_hotkey, self._ptt_pressed.emit)
            try:
                hk.start()
                self._ptt = hk
            except Exception as e:  # noqa: BLE001
                self.tray.notify("Parzprint", f"Tecla de apertar para falar indisponível: {e}")
        elif self.settings.mic_mode != "ptt":
            self._stop_ptt()

    def _stop_ptt(self) -> None:
        self._ptt_timer.stop()
        if self._ptt is not None:
            self._ptt.stop()
            self._ptt = None

    def _audio(self):
        return getattr(self.session, "audio", None) if self.session is not None else None

    def _ptt_pressed_main(self) -> None:
        if self._audio() is not None:
            self._audio().set_mic_open(True)
        self._ptt_timer.start()

    def _ptt_poll(self) -> None:
        key_down = self._key_down
        if key_down is None:
            from ..hotkey import is_key_down as key_down
        if not key_down(self.settings.ptt_hotkey):
            self._ptt_timer.stop()
            if self._audio() is not None:
                self._audio().set_mic_open(False)
