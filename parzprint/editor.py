"""Editor de anotações ligado a um ``SelectionOverlay`` depois da seleção.

As anotações ficam em coordenadas da imagem recortada (pixels físicos, origem no
canto da seleção). Assim a imagem final sai na resolução real do monitor e as
anotações acompanham a seleção se ela for movida.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter
from PySide6.QtWidgets import QLineEdit

from .annotations import (
    DEFAULT_COLOR, AnnotationStack, Arrow, Line, Marker, Pencil, Point, Rect, Text, render,
)
from .capture import crop
from .geometry import place_toolbars
from .qtutil import pil_to_qpixmap
from .toolbar import BottomToolbar, SideToolbar, Tool

TEXT_SIZE = 20


class Editor(QObject):
    closed = Signal()

    def __init__(self, overlay):
        super().__init__(overlay)
        self.ov = overlay
        self.stack = AnnotationStack()
        self.tool: Tool | None = None
        self.color = DEFAULT_COLOR
        self._current = None
        self._base: Image.Image | None = None
        self._committed: Image.Image | None = None
        self._text_edit: QLineEdit | None = None
        self._text_origin: Point | None = None

        self.side = SideToolbar(overlay)
        self.bottom = BottomToolbar(overlay)
        self.side.tool_changed.connect(self._set_tool)
        self.side.color_changed.connect(self._set_color)
        self.side.undo_requested.connect(self.undo)
        self.bottom.close_requested.connect(self.close)
        overlay.selection_changed.connect(self._on_selection_changed)
        overlay.editor = self
        self.side.show()
        self.bottom.show()
        self.reposition()

    # ---------- estado ----------
    @property
    def scale(self) -> float:
        return self.ov.monitor.scale

    def _set_tool(self, tool: Tool | None) -> None:
        self._finish_text()
        self.tool = tool

    def _set_color(self, color: str) -> None:
        self.color = color

    def blocks_selection_change(self) -> bool:
        return False

    def reposition(self) -> None:
        self.side.adjustSize()
        self.bottom.adjustSize()
        side, bottom = place_toolbars(self.ov.sel, self.ov.screen_rect(), self.side.size(), self.bottom.size())
        self.side.move(side)
        self.bottom.move(bottom)

    def _on_selection_changed(self, _rect) -> None:
        self._finish_text()
        self._base = None
        self._committed = None
        self.reposition()

    # ---------- imagens ----------
    def base_image(self) -> Image.Image:
        if self._base is None:
            g = self.ov.selection_global()
            self._base = crop(self.ov.monitor, g.x(), g.y(), g.width(), g.height())
        return self._base

    def _committed_image(self) -> Image.Image:
        if self._committed is None:
            self._committed = render(self.base_image(), self.stack.items())
        return self._committed

    def composite(self) -> Image.Image:
        return render(self.base_image(), self.stack.items())

    def paint(self, p: QPainter) -> None:
        img = self._committed_image()
        if self._current is not None:
            img = render(img, [self._current])
        p.drawPixmap(self.ov.sel.topLeft(), pil_to_qpixmap(img, self.scale))
        self.paint_extra(p)

    def paint_extra(self, p: QPainter) -> None:
        """Ganchos de pintura por cima da imagem (painel de texto)."""

    # ---------- coordenadas ----------
    def to_image(self, pos: QPointF) -> Point:
        s = self.ov.sel
        return Point((pos.x() - s.x()) * self.scale, (pos.y() - s.y()) * self.scale)

    def to_local(self, pt: Point) -> QPoint:
        s = self.ov.sel
        return QPoint(round(s.x() + pt.x / self.scale), round(s.y() + pt.y / self.scale))

    # ---------- mouse ----------
    def cursor_for(self, p: QPoint):
        if self.tool is not None and self.ov.sel.contains(p):
            return Qt.CursorShape.IBeamCursor if self.tool is Tool.TEXT else Qt.CursorShape.CrossCursor
        return None

    def press(self, pos: QPointF) -> bool:
        if self.tool is None or not self.ov.sel.contains(pos.toPoint()):
            return False
        self._finish_text()
        pt = self.to_image(pos)
        w = max(1, round(3 * self.scale))
        if self.tool is Tool.TEXT:
            self._start_text(pos, pt)
        elif self.tool is Tool.PENCIL:
            self._current = Pencil([pt], self.color, w)
        elif self.tool is Tool.MARKER:
            self._current = Marker([pt], self.color, max(1, round(18 * self.scale)))
        elif self.tool is Tool.LINE:
            self._current = Line(pt, pt, self.color, w)
        elif self.tool is Tool.ARROW:
            self._current = Arrow(pt, pt, self.color, w)
        elif self.tool is Tool.RECT:
            self._current = Rect(pt, pt, self.color, w)
        self.ov.update()
        return True

    def move(self, pos: QPointF) -> bool:
        if self._current is None:
            return False
        pt = self._clamped(self.to_image(pos))
        if isinstance(self._current, (Pencil, Marker)):
            self._current.points.append(pt)
        else:
            self._current.end = pt
        self.ov.update()
        return True

    def _clamped(self, pt: Point) -> Point:
        img = self.base_image()
        return Point(min(max(pt.x, 0), img.width - 1), min(max(pt.y, 0), img.height - 1))

    def release(self, pos: QPointF) -> None:
        if self._current is None:
            return
        self.move(pos)
        a, self._current = self._current, None
        if isinstance(a, (Line, Arrow, Rect)) and a.start == a.end:
            self.ov.update()
            return
        self.stack.add(a)
        self._committed = None
        self.ov.update()

    def undo(self) -> None:
        self._finish_text()
        if self.stack.undo() is not None:
            self._committed = None
            self.ov.update()

    # ---------- ferramenta de texto ----------
    def _start_text(self, pos: QPointF, pt: Point) -> None:
        edit = QLineEdit(self.ov)
        f = QFont()
        f.setPixelSize(TEXT_SIZE)
        edit.setFont(f)
        c = QColor(self.color)
        edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,40); color: {c.name()}; border: 1px dashed {c.name()}; }}"
        )
        edit.move(pos.toPoint())
        edit.resize(220, TEXT_SIZE + 10)
        edit.returnPressed.connect(self._finish_text)
        edit.editingFinished.connect(self._finish_text)
        edit.show()
        edit.setFocus()
        self._text_edit = edit
        self._text_origin = pt

    def _finish_text(self) -> None:
        edit, self._text_edit = self._text_edit, None
        if edit is None:
            return
        text = edit.text()
        edit.hide()
        edit.deleteLater()
        if self._text_origin is not None:
            self.stack.add(Text(self._text_origin, text, self.color, round(TEXT_SIZE * self.scale)))
            self._committed = None
        self._text_origin = None
        self.ov.setFocus()
        self.ov.update()

    # ---------- teclado ----------
    def key(self, e) -> bool:
        if e.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return True
        return False

    # ---------- fim ----------
    def close(self) -> None:
        self._finish_text()
        self.closed.emit()
        self.ov.cancelled.emit()  # a sessão fecha a janela
