"""Camada de desenho da gravação: janela transparente sobre a área, gravada junto com a tela.

Fora do modo de desenho os cliques passam para os programas de baixo. No modo de desenho,
a barra lateral de ferramentas aparece (fora do vídeo) e o mouse desenha.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeySequence, QPainter
from PySide6.QtWidgets import QWidget

from ..annotations import DEFAULT_COLOR, Annotation, AnnotationStack, Point, Text, paint_annotation
from ..drawing import DEFAULT_SIZES, TextInput, extend_shape, is_empty, new_shape, step_size
from ..geometry import place_toolbars
from ..toolbar import SideToolbar, Tool
from .exclude import exclude_from_capture

# no modo de desenho a janela precisa de algum pixel para receber o mouse; alfa 1 é invisível
_CATCH = QColor(0, 0, 0, 1)


class DrawLayer(QWidget):
    draw_mode_changed = Signal(bool)

    def __init__(self, area: QRect, items: list[Annotation], scale: float):
        super().__init__(None)
        self.area = QRect(area)
        self.scale = scale
        self.stack = AnnotationStack()
        for a in items:
            self.stack.add(a)
        self.tool: Tool | None = None
        self.color = DEFAULT_COLOR
        self.sizes: dict[Tool, int] = dict(DEFAULT_SIZES)
        self.draw_mode = False
        self._current: Annotation | None = None
        self._text_edit: TextInput | None = None
        self._text_origin: Point | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(area)
        self.toolbar = SideToolbar(None, with_clear=True)
        self.toolbar.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.toolbar.tool_changed.connect(self._set_tool)
        self.toolbar.color_changed.connect(self._set_color)
        self.toolbar.undo_requested.connect(self.undo)
        self.toolbar.clear_requested.connect(self.clear)
        self.toolbar.hide()

    # ------------------------------------------------------------ estado
    def passes_clicks(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)

    def set_draw_mode(self, on: bool) -> None:
        if on == self.draw_mode:
            return
        self._finish_text()
        self.draw_mode = on
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not on)
        self.show()
        if on:
            self.toolbar.show()
            exclude_from_capture(self.toolbar)
            self._place_toolbar()
            self.raise_()
            self.toolbar.raise_()
            self.activateWindow()
            self.setFocus()
            if self.tool is None:
                self.toolbar.buttons[Tool.ARROW].click()
        else:
            self.toolbar.hide()
        self.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        self.update()
        self.draw_mode_changed.emit(on)

    def _place_toolbar(self) -> None:
        screen = QGuiApplication.screenAt(self.area.center()) or QGuiApplication.primaryScreen()
        self.toolbar.adjustSize()
        side, _ = place_toolbars(self.area, screen.geometry(), self.toolbar.size(), self.toolbar.size())
        self.toolbar.move(side)

    def _set_tool(self, tool: Tool | None) -> None:
        self._finish_text()
        self.tool = tool

    def _set_color(self, color: str) -> None:
        self.color = color

    def clear(self) -> None:
        self._finish_text()
        while self.stack.undo() is not None:
            pass
        self.update()

    def undo(self) -> None:
        self._finish_text()
        self.stack.undo()
        self.update()

    def close(self) -> bool:
        self.toolbar.close()
        return super().close()

    # ------------------------------------------------------------ coordenadas
    def to_image(self, pos: QPointF) -> Point:
        return Point(pos.x() * self.scale, pos.y() * self.scale)

    # ------------------------------------------------------------ mouse
    def press(self, pos: QPointF) -> bool:
        if not self.draw_mode or self.tool is None:
            return False
        self._finish_text()
        pt = self.to_image(pos)
        if self.tool is Tool.TEXT:
            self._start_text(pos, pt)
        else:
            self._current = new_shape(self.tool, pt, self.color, max(1, round(self.sizes[self.tool] * self.scale)))
        self.update()
        return True

    def move(self, pos: QPointF) -> bool:
        if self._current is None:
            return False
        extend_shape(self._current, self.to_image(pos))
        self.update()
        return True

    def release(self, pos: QPointF) -> None:
        if self._current is None:
            return
        self.move(pos)
        shape, self._current = self._current, None
        if not is_empty(shape):
            self.stack.add(shape)
        self.update()

    def wheel(self, delta: int) -> bool:
        tool = Tool.TEXT if self._text_edit is not None else self.tool
        if not self.draw_mode or tool is None or delta == 0:
            return False
        self.sizes[tool] = step_size(tool, self.sizes[tool], delta)
        if self._text_edit is not None:
            self._style_text(self._text_edit)
        return True

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press(e.position())

    def mouseMoveEvent(self, e):
        self.move(e.position())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.release(e.position())

    def wheelEvent(self, e):
        if self.wheel(e.angleDelta().y()):
            e.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.set_draw_mode(False)
        elif e.matches(QKeySequence.StandardKey.Undo):
            self.undo()
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------------------ texto
    def _start_text(self, pos: QPointF, pt: Point) -> None:
        edit = TextInput(self)
        edit.move(pos.toPoint() - QPoint(2, 2))
        edit.textChanged.connect(lambda _t, e=edit: self._style_text(e))
        edit.committed.connect(self._finish_text)
        edit.cancelled.connect(self._cancel_text)
        edit.editingFinished.connect(self._finish_text)
        self._style_text(edit)
        edit.show()
        edit.setFocus()
        self._text_edit, self._text_origin = edit, pt

    def _style_text(self, edit: TextInput) -> None:
        size = self.sizes[Tool.TEXT]
        c = QColor(self.color).name()
        edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {c}; border: 1px dashed {c}; padding: 0px 1px; }}"
        )
        f = QFont(edit.font())
        f.setPixelSize(size)
        edit.setFont(f)
        fm = edit.fontMetrics()
        edit.resize(max(60, fm.horizontalAdvance(edit.text() + "  ") + 8), fm.height() + 6)

    def _finish_text(self) -> None:
        edit, self._text_edit = self._text_edit, None
        if edit is None:
            return
        text = edit.text()
        edit.hide()
        edit.deleteLater()
        if self._text_origin is not None:
            self.stack.add(Text(self._text_origin, text, self.color, round(self.sizes[Tool.TEXT] * self.scale)))
        self._text_origin = None
        self.setFocus()
        self.update()

    def _cancel_text(self) -> None:
        self._text_origin = None
        edit, self._text_edit = self._text_edit, None
        if edit is not None:
            edit.hide()
            edit.deleteLater()
        self.setFocus()

    # ------------------------------------------------------------ pintura
    def paintEvent(self, _):
        p = QPainter(self)
        if self.draw_mode:
            p.fillRect(self.rect(), _CATCH)
        p.scale(1 / self.scale, 1 / self.scale)
        for a in self.stack.items():
            paint_annotation(p, a)
        if self._current is not None:
            paint_annotation(p, self._current)
        p.end()
