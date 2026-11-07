"""Barras do editor: lateral (ferramentas) e inferior (ações), no estilo do Lightshot."""

from __future__ import annotations

import math
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QColorDialog, QHBoxLayout, QLabel, QMenu, QToolButton, QVBoxLayout, QWidget

from .annotations import DEFAULT_COLOR, PALETTE

BUTTON = 30
ICON = 20
FG = QColor("#EEEEEE")

STYLE = """
QWidget#bar { background: rgba(32, 32, 32, 235); border: 1px solid rgba(255,255,255,40); border-radius: 6px; }
QToolButton { background: transparent; border: none; border-radius: 4px; padding: 2px; }
QToolButton:hover { background: rgba(255,255,255,30); }
QToolButton:checked { background: rgba(30,136,229,170); }
QToolButton:disabled { opacity: 0.4; }
QLabel { color: #EEEEEE; padding: 0 6px; }
"""


class Tool(Enum):
    PENCIL = "Lápis"
    LINE = "Linha"
    ARROW = "Seta"
    RECT = "Retângulo"
    MARKER = "Marca-texto"
    TEXT = "Texto"


def _pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _arrow_head(p: QPainter, a: QPointF, b: QPointF, size: float = 6) -> None:
    ang = math.atan2(b.y() - a.y(), b.x() - a.x())
    left = QPointF(b.x() - size * math.cos(ang - 0.5), b.y() - size * math.sin(ang - 0.5))
    right = QPointF(b.x() - size * math.cos(ang + 0.5), b.y() - size * math.sin(ang + 0.5))
    p.drawPolygon(QPolygonF([b, left, right]))


def make_icon(name: str, color: QColor = FG) -> QIcon:
    """Ícones simples desenhados com QPainter (sem arquivos de imagem)."""
    pm = QPixmap(ICON * 2, ICON * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen(color))
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = ICON
    if name == "pencil":
        p.drawLine(QPointF(4, 16), QPointF(15, 5))
        p.drawLine(QPointF(13, 3), QPointF(17, 7))
        p.drawLine(QPointF(4, 16), QPointF(3, 17))
    elif name == "line":
        p.drawLine(QPointF(4, 16), QPointF(16, 4))
    elif name == "arrow":
        p.setBrush(color)
        p.drawLine(QPointF(4, 16), QPointF(14, 6))
        _arrow_head(p, QPointF(4, 16), QPointF(16, 4))
    elif name == "rect":
        p.drawRect(QRectF(4, 5, 12, 10))
    elif name == "marker":
        p.setPen(_pen(QColor(253, 216, 53, 200), 6))
        p.drawLine(QPointF(4, 14), QPointF(16, 6))
    elif name == "text":
        f = QFont()
        f.setPixelSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "T")
    elif name == "undo":
        p.drawArc(QRectF(5, 5, 11, 10), 90 * 16, -230 * 16)
        p.setBrush(color)
        _arrow_head(p, QPointF(11, 3), QPointF(6, 5), 5)
    elif name == "save":
        p.drawLine(QPointF(10, 3), QPointF(10, 12))
        p.drawPolyline(QPolygonF([QPointF(6, 8), QPointF(10, 12), QPointF(14, 8)]))
        p.drawPolyline(QPolygonF([QPointF(4, 13), QPointF(4, 16), QPointF(16, 16), QPointF(16, 13)]))
    elif name == "copy":
        p.drawRect(QRectF(7, 7, 9, 10))
        p.drawPolyline(QPolygonF([QPointF(4, 13), QPointF(4, 3), QPointF(12, 3)]))
    elif name == "print":
        p.drawRect(QRectF(3, 8, 14, 6))
        p.drawPolyline(QPolygonF([QPointF(6, 8), QPointF(6, 3), QPointF(14, 3), QPointF(14, 8)]))
        p.drawRect(QRectF(6, 12, 8, 5))
    elif name == "ocr":
        pen = _pen(color, 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(2.5, 2.5, 15, 15))
        p.setPen(_pen(color))
        p.drawLine(QPointF(6, 7), QPointF(14, 7))
        p.drawLine(QPointF(6, 10), QPointF(14, 10))
        p.drawLine(QPointF(6, 13), QPointF(11, 13))
    elif name == "close":
        p.drawLine(QPointF(5, 5), QPointF(15, 15))
        p.drawLine(QPointF(15, 5), QPointF(5, 15))
    p.end()
    return QIcon(pm)


def color_icon(color: str) -> QIcon:
    pm = QPixmap(ICON * 2, ICON * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#EEEEEE"), 1.5))
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(3, 3, 14, 14), 3, 3)
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
            b = _button(self, make_icon(icon), tool.value, checkable=True)
            b.clicked.connect(lambda checked, t=tool: self._on_tool(t, checked))
            lay.addWidget(b)
            self.buttons[tool] = b
        self.color = DEFAULT_COLOR
        self.color_button = _button(self, color_icon(self.color), "Cor")
        self.color_button.clicked.connect(self._open_colors)
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

    def _open_colors(self) -> None:
        menu = QMenu(self)
        for c in PALETTE:
            act = QAction(color_icon(c), c, menu)
            act.triggered.connect(lambda _=False, c=c: self.set_color(c))
            menu.addAction(act)
        menu.addSeparator()
        more = menu.addAction("Mais cores…")
        more.triggered.connect(self._more_colors)
        menu.exec(self.color_button.mapToGlobal(self.color_button.rect().topRight()))

    def _more_colors(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self.window(), "Escolher cor")
        if c.isValid():
            self.set_color(c.name().upper())

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
