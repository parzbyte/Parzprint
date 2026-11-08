"""Barras do editor: lateral (ferramentas) e inferior (ações), no estilo do Lightshot."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .annotations import DEFAULT_COLOR
from .colordialog import choose_color

BUTTON = 32
ICON = 20
FG = "#ECECEC"
FG_DISABLED = "#6E6E6E"

STYLE = """
QWidget#bar { background: rgba(28, 28, 30, 240); border: 1px solid rgba(255,255,255,38); border-radius: 7px; }
QToolButton { background: transparent; border: none; border-radius: 5px; padding: 0px; }
QToolButton:hover { background: rgba(255,255,255,28); }
QToolButton:pressed { background: rgba(255,255,255,45); }
QToolButton:checked { background: rgba(30,136,229,200); }
QLabel { color: #ECECEC; padding: 0 6px; }
"""


class Tool(Enum):
    PENCIL = "Lápis"
    LINE = "Linha"
    ARROW = "Seta"
    RECT = "Retângulo"
    MARKER = "Marca-texto"
    TEXT = "Texto"


# Ícones de traço (grade 24x24, traço 2, pontas arredondadas). Desenhados para este app.
_SVG = {
    "pencil": '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/><path d="m14.5 5.5 3 3"/>',
    "line": '<path d="M5 19 19 5"/>',
    "arrow": '<path d="M5 19 18 6"/><path d="M9.5 5H19v9.5" />',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="1.5"/>',
    "marker": '<path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
    "text": '<path d="M5 7V5h14v2"/><path d="M12 5v14"/><path d="M9 19h6"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "save": '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    "print": '<path d="M7 9V3h10v6"/><path d="M7 18H5a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7" rx="1"/>',
    "ocr": '<path d="M3 8V5a2 2 0 0 1 2-2h3"/><path d="M16 3h3a2 2 0 0 1 2 2v3"/><path d="M21 16v3a2 2 0 0 1-2 2h-3"/><path d="M8 21H5a2 2 0 0 1-2-2v-3"/><path d="M7.5 8.5h9"/><path d="M12 8.5v7"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}


def _svg(name: str, color: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{_SVG[name]}</svg>"
    ).encode()


def _pixmap(svg: bytes, size: int = ICON, ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(round(size * ratio), round(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg)).render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def make_icon(name: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_pixmap(_svg(name, FG)), QIcon.Mode.Normal)
    icon.addPixmap(_pixmap(_svg(name, FG_DISABLED)), QIcon.Mode.Disabled)
    return icon


def color_icon(color: str) -> QIcon:
    """Bolinha com a cor atual, com contorno claro (visível sobre qualquer cor)."""
    ratio = 2.0
    pm = QPixmap(round(ICON * ratio), round(ICON * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(FG), 1.5))
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(3, 3, ICON - 6, ICON - 6))
    p.end()
    return QIcon(pm)


def _button(parent: QWidget, icon: QIcon, tip: str, checkable: bool = False) -> QToolButton:
    b = QToolButton(parent)
    b.setIcon(icon)
    b.setIconSize(QSize(ICON, ICON))
    b.setFixedSize(BUTTON, BUTTON)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


class _Bar(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)


class SideToolbar(_Bar):
    tool_changed = Signal(object)  # Tool | None
    color_changed = Signal(str)
    undo_requested = Signal()

    _ICONS = {
        Tool.PENCIL: "pencil", Tool.LINE: "line", Tool.ARROW: "arrow",
        Tool.RECT: "rect", Tool.MARKER: "marker", Tool.TEXT: "text",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.buttons: dict[Tool, QToolButton] = {}
        for tool, icon in self._ICONS.items():
            tip = f"{tool.value} (roda do mouse muda o tamanho)"
            b = _button(self, make_icon(icon), tip, checkable=True)
            b.clicked.connect(lambda checked, t=tool: self._on_tool(t, checked))
            lay.addWidget(b)
            self.buttons[tool] = b
        self.color = DEFAULT_COLOR
        self.color_button = _button(self, color_icon(self.color), "Cor")
        self.color_button.clicked.connect(self.open_colors)
        lay.addWidget(self.color_button)
        self.undo_button = _button(self, make_icon("undo"), "Desfazer (Ctrl+Z)")
        self.undo_button.clicked.connect(self.undo_requested)
        lay.addWidget(self.undo_button)
        self.adjustSize()

    def _on_tool(self, tool: Tool, checked: bool) -> None:
        for t, b in self.buttons.items():
            if t is not tool:
                b.setChecked(False)
        self.tool_changed.emit(tool if checked else None)

    def set_tool(self, tool: Tool | None) -> None:
        for t, b in self.buttons.items():
            b.setChecked(t is tool)
        self.tool_changed.emit(tool)

    def set_color(self, color: str) -> None:
        self.color = color
        self.color_button.setIcon(color_icon(color))
        self.color_changed.emit(color)

    def open_colors(self) -> None:
        chosen = choose_color(self.color, self)
        if chosen:
            self.set_color(chosen)
        w = self.window()
        w.activateWindow()
        w.setFocus()

    def set_tools_enabled(self, enabled: bool) -> None:
        for b in [*self.buttons.values(), self.color_button, self.undo_button]:
            b.setEnabled(enabled)


class BottomToolbar(_Bar):
    save_requested = Signal()
    copy_requested = Signal()
    print_requested = Signal()
    text_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.busy_label = QLabel(self)
        self.busy_label.hide()
        lay.addWidget(self.busy_label)
        specs = [
            ("save", "Salvar (Ctrl+S)", self.save_requested),
            ("copy", "Copiar imagem (Ctrl+C)", self.copy_requested),
            ("print", "Imprimir", self.print_requested),
            ("ocr", "Texto: extrair o texto da imagem", self.text_requested),
            ("close", "Fechar (Esc)", self.close_requested),
        ]
        self.buttons: dict[str, QToolButton] = {}
        for icon, tip, signal in specs:
            b = _button(self, make_icon(icon), tip)
            b.clicked.connect(signal)
            lay.addWidget(b)
            self.buttons[icon] = b
        self.text_button = self.buttons["ocr"]
        self.adjustSize()

    def set_busy(self, busy: bool, label: str = "") -> None:
        self.text_button.setEnabled(not busy)
        self.busy_label.setText(label)
        self.busy_label.setVisible(busy and bool(label))
        self.adjustSize()
