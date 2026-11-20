"""Barrinha da gravação: tempo, microfone, som do PC, desenhar, pausar e parar (fora do vídeo)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QWidget

from ..settings import Settings
from ..toolbar import STYLE, _button, make_icon
from .exclude import exclude_from_capture

GAP = 6
MARGIN = 12
WARNING_MS = 5000
MODES = [("off", "Microfone desligado"), ("always", "Sempre ligado"), ("ptt", "Apertar para falar")]

BAR_STYLE = STYLE + """
QComboBox { background: rgba(255,255,255,18); color: #ECECEC; border: 1px solid rgba(255,255,255,40);
            border-radius: 5px; padding: 3px 8px; min-height: 22px; }
QComboBox QAbstractItemView { background: #2C2C2E; color: #ECECEC; selection-background-color: #1E88E5; }
QLabel#time { color: #FFFFFF; font-weight: bold; padding: 0 8px; }
QLabel#warn { color: #FFB74D; padding: 0 6px; }
"""


def bar_position(area: QRect, screen: QRect, size: QSize) -> QPoint:
    """Embaixo da área; se não couber, em cima; se nada couber, no canto do monitor."""
    w, h = size.width(), size.height()
    s_right, s_bottom = screen.x() + screen.width(), screen.y() + screen.height()
    x = min(max(area.x(), screen.x()), s_right - w)
    below = area.y() + area.height() + GAP
    if below + h <= s_bottom:
        return QPoint(x, below)
    above = area.y() - GAP - h
    if above >= screen.y():
        return QPoint(x, above)
    return QPoint(s_right - w - MARGIN, s_bottom - h - MARGIN)


class RecordBar(QWidget):
    settings_changed = Signal(object)  # Settings

    def __init__(self, session, settings: Settings, layer, mics: list[tuple[str, str]] | None = None):
        super().__init__(None)
        self.session = session
        self.settings = settings
        self.layer = layer
        self.setObjectName("bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setStyleSheet(BAR_STYLE)
        if mics is None:
            from .audio import list_microphones

            mics = list_microphones()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)
        self.time_label = QLabel("● 00:00", self)
        self.time_label.setObjectName("time")
        lay.addWidget(self.time_label)

        lay.addWidget(self._icon_label("mic"))
        self.mic_combo = QComboBox(self)
        for dev_id, name in mics:
            self.mic_combo.addItem(name, dev_id)
        self.mic_combo.addItem("Nenhum microfone", "")
        idx = self.mic_combo.findData(settings.mic_device)
        self.mic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mic_combo.currentIndexChanged.connect(self._on_mic)
        lay.addWidget(self.mic_combo)

        self.mode_combo = QComboBox(self)
        for key, label in MODES:
            self.mode_combo.addItem(label, key)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(settings.mic_mode)))
        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        lay.addWidget(self.mode_combo)

        self.sys_button = _button(self, make_icon("speaker"), "Gravar o som do computador", checkable=True)
        self.sys_button.setChecked(settings.system_audio)
        self.sys_button.toggled.connect(self._on_sys)
        lay.addWidget(self.sys_button)

        self.draw_button = _button(self, make_icon("draw"), "Desenhar na tela durante a gravação", checkable=True)
        self.draw_button.toggled.connect(self._on_draw)
        layer.draw_mode_changed.connect(self._on_layer_draw)
        lay.addWidget(self.draw_button)

        self.pause_button = _button(self, make_icon("pause"), "Pausar")
        self.pause_button.clicked.connect(self._on_pause)
        lay.addWidget(self.pause_button)
        self.stop_button = _button(self, make_icon("stop"), "Parar e salvar")
        self.stop_button.clicked.connect(session.stop)
        lay.addWidget(self.stop_button)

        self.warning_label = QLabel(self)
        self.warning_label.setObjectName("warn")
        self.warning_label.hide()
        lay.addWidget(self.warning_label)
        self._warn_timer = QTimer(self)
        self._warn_timer.setSingleShot(True)
        self._warn_timer.timeout.connect(self._hide_warning)

        session.warning.connect(self.show_warning)
        session.state_changed.connect(self._on_state)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.adjustSize()

    def _icon_label(self, name: str) -> QLabel:
        lbl = QLabel(self)
        lbl.setPixmap(make_icon(name).pixmap(QSize(18, 18)))
        return lbl

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)

    # ------------------------------------------------------------ ações
    def _audio(self):
        return getattr(self.session, "audio", None)

    def _changed(self) -> None:
        self.settings_changed.emit(self.settings)

    def _on_mic(self, _i: int) -> None:
        dev_id = self.mic_combo.currentData() or ""
        self.settings.mic_device = dev_id
        if self._audio() is not None:
            self._audio().set_mic(dev_id or None)
        self._changed()

    def _on_mode(self, _i: int) -> None:
        mode = self.mode_combo.currentData()
        self.settings.mic_mode = mode
        if self._audio() is not None:
            self._audio().set_mic_open(mode == "always")
        self._changed()

    def _on_sys(self, on: bool) -> None:
        self.settings.system_audio = on
        if self._audio() is not None:
            self._audio().set_system_audio(on)
        self._changed()

    def _on_draw(self, on: bool) -> None:
        if self.layer.draw_mode != on:
            self.layer.set_draw_mode(on)

    def _on_layer_draw(self, on: bool) -> None:
        if self.draw_button.isChecked() != on:
            self.draw_button.blockSignals(True)
            self.draw_button.setChecked(on)
            self.draw_button.blockSignals(False)

    def _on_pause(self) -> None:
        if self.session.state == "paused":
            self.session.resume()
        else:
            self.session.pause()

    def _on_state(self, state: str) -> None:
        paused = state == "paused"
        self.pause_button.setIcon(make_icon("play" if paused else "pause"))
        self.pause_button.setToolTip("Continuar" if paused else "Pausar")
        self.refresh()

    # ------------------------------------------------------------ tela
    def refresh(self) -> None:
        secs = self.session.elapsed_ms() // 1000
        dot = "❚❚" if self.session.state == "paused" else "●"
        self.time_label.setText(f"{dot} {secs // 60:02d}:{secs % 60:02d}")

    def show_warning(self, text: str) -> None:
        self.warning_label.setText(text)
        self.warning_label.show()
        self.adjustSize()
        self._warn_timer.start(WARNING_MS)

    def _hide_warning(self) -> None:
        self.warning_label.hide()
        self.adjustSize()

    def place(self, area: QRect) -> None:
        self.adjustSize()
        screen = QGuiApplication.screenAt(area.center()) or QGuiApplication.primaryScreen()
        self.move(bar_position(area, screen.geometry(), self.size()))
