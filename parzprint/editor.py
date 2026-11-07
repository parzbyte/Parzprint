"""Editor de anotações ligado a um ``SelectionOverlay`` depois da seleção.

As anotações ficam em coordenadas da imagem recortada (pixels físicos, origem no
canto da seleção). Assim a imagem final sai na resolução real do monitor e as
anotações acompanham a seleção se ela for movida.
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image
from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QMessageBox

from .annotations import (
    DEFAULT_COLOR, AnnotationStack, Arrow, Line, Marker, Pencil, Point, Rect, Text, render,
)
from .capture import crop
from .export import ask_save_path, copy_image, copy_text, print_image, save_image
from .geometry import place_panel, place_toolbars
from .ocr import OcrEngine, get_engine
from .ocr_worker import OcrWorker, progress_label
from .qtutil import pil_to_qpixmap
from .settings import Settings
from .textpanel import TextPanel, TextSelectionModel
from .toolbar import BottomToolbar, SideToolbar, Tool

TEXT_SIZE = 20
PANEL_SIZE = QSize(420, 440)
BOX_FILL = QColor(30, 136, 229, 64)
BOX_SELECTED = QColor(30, 136, 229, 128)
BOX_HOVER = QColor("#1E88E5")


class _TextInput(QLineEdit):
    """Campo da ferramenta Texto: Enter confirma e Esc cancela, sem repassar a tecla
    para o overlay (onde Enter copiaria a imagem e Esc fecharia a captura)."""

    committed = Signal()
    cancelled = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            e.accept()
            self.committed.emit()
            return
        if e.key() == Qt.Key.Key_Escape:
            e.accept()
            self.cancelled.emit()
            return
        super().keyPressEvent(e)


class Editor(QObject):
    closed = Signal()

    def __init__(self, overlay, settings: Settings | None = None, engine_provider=None):
        super().__init__(overlay)
        self.ov = overlay
        self.settings = settings or Settings()
        self._engine_provider = engine_provider or (lambda: get_engine(self.settings.ocr_engine))
        self._ocr_blocks: list | None = None
        self._model: TextSelectionModel | None = None
        self.panel: TextPanel | None = None
        self._hover: int | None = None
        self._drag_start: Point | None = None
        self._ocr_running = False
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
        self.bottom.save_requested.connect(self.save)
        self.bottom.copy_requested.connect(self.copy)
        self.bottom.print_requested.connect(self.print_)
        self.bottom.text_requested.connect(self.request_text)
        self._last_sel = QRect(overlay.sel)
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

    @property
    def text_mode(self) -> bool:
        return self.panel is not None and self.panel.isVisible()

    def blocks_selection_change(self) -> bool:
        return self.text_mode or self._ocr_running

    def reposition(self) -> None:
        self.side.adjustSize()
        self.bottom.adjustSize()
        side, bottom = place_toolbars(self.ov.sel, self.ov.screen_rect(), self.side.size(), self.bottom.size())
        self.side.move(side)
        self.bottom.move(bottom)
        if self.panel is not None:
            screen = self.ov.screen_rect()
            size = QSize(PANEL_SIZE.width(), min(PANEL_SIZE.height(), screen.height() - 20))
            self.panel.resize(size)
            self.panel.move(place_panel(self.ov.sel, screen, size, self.side.geometry()))

    def _on_selection_changed(self, _rect) -> None:
        self._finish_text()
        new, old = QRect(self.ov.sel), self._last_sel
        self._last_sel = new
        if new == old:
            return
        if new.size() != old.size():
            # redimensionou: as anotações ficam sobre o mesmo conteúdo da tela
            # (mover a seleção inteira, sem mudar o tamanho, leva as anotações junto)
            dx = (old.x() - new.x()) * self.scale
            dy = (old.y() - new.y()) * self.scale
            if dx or dy:
                self.stack.translate(dx, dy)
        self._base = None
        self._committed = None
        self._ocr_blocks = None
        self._model = None
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
        """Caixas dos blocos de texto por cima da imagem, quando o painel está aberto."""
        if not self.text_mode or self._model is None:
            return
        selected = set(self._model.selected_indices())
        for i in range(len(self._model.blocks)):
            r = self.block_rect(i)
            p.fillRect(r, BOX_SELECTED if i in selected else BOX_FILL)
            if i == self._hover:
                p.setPen(QPen(BOX_HOVER, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r)

    def block_rect(self, i: int) -> QRect:
        b = self._model.blocks[i]
        tl = self.to_local(Point(b.x, b.y))
        br = self.to_local(Point(b.x + b.width, b.y + b.height))
        return QRect(tl, br).adjusted(-1, -1, 1, 1)

    # ---------- coordenadas ----------
    def to_image(self, pos: QPointF) -> Point:
        s = self.ov.sel
        return Point((pos.x() - s.x()) * self.scale, (pos.y() - s.y()) * self.scale)

    def to_local(self, pt: Point) -> QPoint:
        s = self.ov.sel
        return QPoint(round(s.x() + pt.x / self.scale), round(s.y() + pt.y / self.scale))

    # ---------- mouse ----------
    def cursor_for(self, p: QPoint):
        if self.text_mode:
            return Qt.CursorShape.IBeamCursor if self.ov.sel.contains(p) else Qt.CursorShape.ArrowCursor
        if self.tool is not None and self.ov.sel.contains(p):
            return Qt.CursorShape.IBeamCursor if self.tool is Tool.TEXT else Qt.CursorShape.CrossCursor
        return None

    def press(self, pos: QPointF) -> bool:
        if self.text_mode:
            if self.ov.sel.contains(pos.toPoint()):
                self._drag_start = self.to_image(pos)
            return True
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
        if self.text_mode:
            self._text_mode_move(pos)
            return True
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
        if self.text_mode:
            self._text_mode_release(pos)
            return
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
        edit = _TextInput(self.ov)
        f = QFont()
        f.setPixelSize(TEXT_SIZE)
        edit.setFont(f)
        c = QColor(self.color)
        edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,40); color: {c.name()}; border: 1px dashed {c.name()}; }}"
        )
        edit.move(pos.toPoint())
        edit.resize(220, TEXT_SIZE + 10)
        edit.committed.connect(self._finish_text)
        edit.cancelled.connect(self._cancel_text)
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

    def _cancel_text(self) -> None:
        """Esc no campo de texto descarta só o texto, não a captura."""
        self._text_origin = None
        edit, self._text_edit = self._text_edit, None
        if edit is not None:
            edit.hide()
            edit.deleteLater()
        self.ov.setFocus()
        self.ov.update()

    # ---------- teclado ----------
    def key(self, e) -> bool:
        if self.text_mode and e.matches(QKeySequence.StandardKey.Copy):
            # com o painel aberto, Ctrl+C é sobre texto; sem seleção não faz nada
            self._copy_selected_text()
        elif e.matches(QKeySequence.StandardKey.Undo):
            self.undo()
        elif e.matches(QKeySequence.StandardKey.Copy):
            self.copy()
        elif e.matches(QKeySequence.StandardKey.Save):
            self.save()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.copy()
        else:
            return False
        return True

    # ---------- texto (OCR) ----------
    def request_text(self) -> None:
        self._finish_text()
        if self._ocr_running:
            return
        self._ensure_panel()
        if self._ocr_blocks is not None:
            self._open_panel()
            return
        try:
            engine: OcrEngine = self._engine_provider()
        except Exception as e:  # noqa: BLE001
            self._open_panel()
            self.panel.show_error(str(e))
            return
        label = progress_label(engine)
        self._ocr_running = True
        self.bottom.set_busy(True, label)
        self.reposition()
        worker = OcrWorker(engine, self.base_image())
        worker.finished_ok.connect(self._on_ocr_done)
        worker.failed.connect(self._on_ocr_failed)
        worker.start()

    def _ensure_panel(self) -> None:
        if self.panel is not None:
            return
        self.panel = TextPanel(self.ov)
        self.panel.hide()
        self.panel.hover_block.connect(self._on_panel_hover)
        self.panel.copy_all.connect(copy_text)
        self.panel.copy_selection.connect(self._copy_selected_text)
        self.panel.closed.connect(self.close_panel)
        self.panel.retry.connect(self._retry)

    def _open_panel(self) -> None:
        self.tool = None
        self.side.set_tool(None)
        self.side.set_tools_enabled(False)
        self._model = TextSelectionModel(self._ocr_blocks or [])
        self._hover = None
        self.panel.show_blocks(self._ocr_blocks or [])
        self.panel.show()
        self.panel.raise_()
        self.reposition()
        self.ov.update()

    def _on_ocr_done(self, blocks: list) -> None:
        self._ocr_running = False
        self.bottom.set_busy(False)
        self._ocr_blocks = blocks
        self._open_panel()

    def _on_ocr_failed(self, message: str) -> None:
        self._ocr_running = False
        self.bottom.set_busy(False)
        self._ocr_blocks = None
        self._open_panel()
        self.panel.show_error(message)

    def _retry(self) -> None:
        self.close_panel()
        self.request_text()

    def close_panel(self) -> None:
        if self.panel is not None:
            self.panel.hide()
        self._hover = None
        self._drag_start = None
        self.side.set_tools_enabled(True)
        self.ov.setFocus()
        self.ov.update()

    def _on_panel_hover(self, i) -> None:
        if self._model is None or (i is not None and not 0 <= i < len(self._model.blocks)):
            i = None
        if i != self._hover:
            self._hover = i
            self.ov.update()

    def _text_mode_move(self, pos: QPointF) -> None:
        if self._model is None:
            return
        pt = self.to_image(pos)
        if self._drag_start is not None:
            a = self._drag_start
            self._model.select_range_by_drag((round(a.x), round(a.y), round(pt.x - a.x), round(pt.y - a.y)))
            self.panel.set_selection_count(len(self._model.selected_indices()))
        hit = self._model.hit(round(pt.x), round(pt.y)) if self.ov.sel.contains(pos.toPoint()) else None
        if hit != self._hover:
            self._hover = hit
            self.panel.highlight_block(hit)
        self.ov.update()

    def _text_mode_release(self, pos: QPointF) -> None:
        if self._model is None or self._drag_start is None:
            return
        a, self._drag_start = self._drag_start, None
        pt = self.to_image(pos)
        if abs(pt.x - a.x) < 3 * self.scale and abs(pt.y - a.y) < 3 * self.scale:
            hit = self._model.hit(round(pt.x), round(pt.y))
            if hit is None:
                self._model.clear()
            else:
                self._model.select_only(hit)
        self.panel.set_selection_count(len(self._model.selected_indices()))
        self.ov.update()

    def _copy_selected_text(self) -> None:
        if self._model is not None and self._model.selected_indices():
            copy_text(self._model.selected_text())

    # ---------- ações ----------
    def save(self) -> bool:
        self._finish_text()
        path = ask_save_path(self.ov, self.settings, datetime.now())
        if path is None:
            return False
        try:
            save_image(self.composite(), path, self.settings.image_format)
        except OSError as e:
            QMessageBox.critical(self.ov, "Parzprint", f"Não foi possível salvar em\n{path}\n\n{e}")
            return False
        self.close()
        return True

    def copy(self) -> None:
        self._finish_text()
        copy_image(self.composite())
        self.close()

    def print_(self) -> None:
        self._finish_text()
        print_image(self.composite(), self.ov)
        self.ov.activateWindow()
        self.ov.setFocus()

    # ---------- fim ----------
    def close(self) -> None:
        self._finish_text()
        self.closed.emit()
        self.ov.cancelled.emit()  # a sessão fecha a janela
