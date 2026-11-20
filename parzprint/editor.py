"""Editor de anotações ligado a um ``SelectionOverlay`` depois da seleção.

As anotações ficam em coordenadas da imagem recortada (pixels físicos, origem no
canto da seleção). Assim a imagem final sai na resolução real do monitor e as
anotações acompanham a seleção se ela for movida.
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image
from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QRegion
from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton

from .annotations import (
    DEFAULT_COLOR, AnnotationStack, Point, Text, paint_annotation, render,
)
from .capture import crop
from .export import ask_save_path, copy_image, copy_text, print_image, save_image
from .geometry import place_panel, place_toolbars
from .ocr import OcrEngine, get_engine
from .ocr_worker import OcrWorker, progress_label
from .qtutil import pil_to_qpixmap
from .settings import Settings
from .drawing import DEFAULT_SIZES, TextInput, extend_shape, is_empty, new_shape, step_size
from .textpanel import TextLayout, TextPanel
from .toolbar import BottomToolbar, SideToolbar, Tool

HUD_MS = 900
PANEL_SIZE = QSize(420, 440)
LENS_DIM = QColor(0, 0, 0, 110)  # escurece a imagem fora do texto, como no Google Lens
LENS_SELECTION = QColor(30, 136, 229, 120)
CHIP_STYLE = """
QPushButton { background: #1E88E5; color: white; border: none; border-radius: 15px;
              padding: 6px 16px; font-weight: bold; }
QPushButton:hover { background: #2196F3; }
"""


class Editor(QObject):
    closed = Signal()

    def __init__(self, overlay, settings: Settings | None = None, engine_provider=None):
        super().__init__(overlay)
        self.ov = overlay
        self.settings = settings or Settings()
        self._engine_provider = engine_provider or (lambda: get_engine(self.settings.ocr_engine))
        self._ocr_blocks: list | None = None
        self.layout: TextLayout | None = None
        self._anchor: int | None = None
        self.panel: TextPanel | None = None
        self._ocr_running = False
        self.stack = AnnotationStack()
        self.tool: Tool | None = None
        self.color = DEFAULT_COLOR
        self.sizes: dict[Tool, int] = dict(DEFAULT_SIZES)
        self._committed_pixmap = None
        self._committed_pixmap_src = None
        self._hud_pos: QPointF | None = None
        self._hud_timer = QTimer(self)
        self._hud_timer.setSingleShot(True)
        self._hud_timer.timeout.connect(self._hide_hud)
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
        self.layout = None
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
        if self._committed_pixmap_src is not img:
            self._committed_pixmap = pil_to_qpixmap(img, self.scale)
            self._committed_pixmap_src = img
        p.drawPixmap(self.ov.sel.topLeft(), self._committed_pixmap)
        if self._current is not None:
            # o traço em andamento é desenhado direto na tela, com o mesmo código da imagem final
            p.save()
            p.setClipRect(self.ov.sel)
            p.translate(self.ov.sel.topLeft())
            p.scale(1 / self.scale, 1 / self.scale)
            paint_annotation(p, self._current)
            p.restore()
        self.paint_extra(p)
        self._paint_hud(p)

    # ---------- tamanho da ferramenta (roda do mouse) ----------
    def wheel(self, delta: int, pos: QPointF | None = None) -> bool:
        tool = Tool.TEXT if self._text_edit is not None else self.tool
        if tool is None or self.text_mode or delta == 0:
            return False
        self.sizes[tool] = step_size(tool, self.sizes[tool], delta)
        if self._text_edit is not None:
            self._style_text_edit(self._text_edit)
        if pos is not None:
            self._hud_pos = QPointF(pos)
        elif self._hud_pos is None:
            self._hud_pos = QPointF(self.ov.sel.center())
        self._hud_tool = tool
        self._hud_timer.start(HUD_MS)
        self.ov.update()
        return True

    def _hide_hud(self) -> None:
        self._hud_pos = None
        self.ov.update()

    def _paint_hud(self, p: QPainter) -> None:
        if self._hud_pos is None:
            return
        tool = self._hud_tool
        size = self.sizes[tool]
        c = QPointF(self._hud_pos)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if tool is not Tool.TEXT:
            r = max(size, 2) / 2
            p.setPen(QPen(QColor(255, 255, 255, 230), 1))
            fill = QColor(self.color)
            fill.setAlpha(100 if tool is Tool.MARKER else 220)
            p.setBrush(fill)
            p.drawEllipse(c, r, r)
        label = f"{size} px"
        f = QFont()
        f.setPixelSize(12)
        p.setFont(f)
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(label) + 12, fm.height() + 6
        box = QRect(round(c.x() + size / 2 + 8), round(c.y() - h / 2), w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 190))
        p.drawRoundedRect(box, 4, 4)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        p.restore()

    def paint_extra(self, p: QPainter) -> None:
        """Modo texto: imagem levemente escurecida fora das linhas e a seleção em azul."""
        if not self.text_mode or self.layout is None:
            return
        p.save()
        p.setClipRect(self.ov.sel)
        dim = QRegion(self.ov.sel)
        for b in self.layout.blocks:
            dim = dim.subtracted(QRegion(self._local_rect(b.x - 2, b.y - 2, b.x + b.width + 2, b.y + b.height + 2)))
        p.setClipRegion(dim)
        p.fillRect(self.ov.sel, LENS_DIM)
        p.setClipRect(self.ov.sel)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(LENS_SELECTION)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for x0, y0, x1, y1 in self.layout.selection_rects():
            p.drawRoundedRect(QRectF(self._local_rect(x0, y0 - 1, x1, y1 + 1)), 3, 3)
        p.restore()

    def _local_rect(self, x0: float, y0: float, x1: float, y1: float) -> QRect:
        return QRect(self.to_local(Point(x0, y0)), self.to_local(Point(x1, y1)))

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
            # cursor de inserção em toda a área: dá para começar a seleção de qualquer ponto
            return Qt.CursorShape.IBeamCursor if self.ov.sel.contains(p) else Qt.CursorShape.ArrowCursor
        if self.tool is not None and self.ov.sel.contains(p):
            return Qt.CursorShape.IBeamCursor if self.tool is Tool.TEXT else Qt.CursorShape.CrossCursor
        return None

    def press(self, pos: QPointF) -> bool:
        if self.text_mode:
            if self.layout is not None and self.ov.sel.contains(pos.toPoint()):
                pt = self.to_image(pos)
                self._anchor = self.layout.position_at(pt.x, pt.y)
                self.layout.select(self._anchor, self._anchor)
                self.copy_chip.hide()
                self._sync_panel()
                self.ov.update()
            return True
        if self.tool is None or not self.ov.sel.contains(pos.toPoint()):
            return False
        self._finish_text()
        pt = self.to_image(pos)
        w = max(1, round(self.sizes.get(self.tool, 3) * self.scale))
        if self.tool is Tool.TEXT:
            self._start_text(pos, pt)
        else:
            self._current = new_shape(self.tool, pt, self.color, w)
        self.ov.update()
        return True

    def move(self, pos: QPointF) -> bool:
        if self.text_mode:
            self._text_mode_move(pos)
            return True
        if self._current is None:
            return False
        extend_shape(self._current, self._clamped(self.to_image(pos)))
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
        if is_empty(a):
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
        edit = TextInput(self.ov)
        edit.setTextMargins(0, 0, 0, 0)
        edit.move(pos.toPoint() - QPoint(2, 2))
        edit.textChanged.connect(lambda _t, e=edit: self._style_text_edit(e))
        self._style_text_edit(edit)
        edit.committed.connect(self._finish_text)
        edit.cancelled.connect(self._cancel_text)
        edit.editingFinished.connect(self._finish_text)
        edit.show()
        edit.setFocus()
        self._text_edit = edit
        self._text_origin = pt

    def _style_text_edit(self, edit: QLineEdit) -> None:
        size = self.sizes[Tool.TEXT]
        c = QColor(self.color).name()
        edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {c}; border: 1px dashed {c};"
            f" padding: 0px 1px; font-size: {size}px; }}"
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
        elif self.text_mode and e.matches(QKeySequence.StandardKey.SelectAll):
            self.layout.select_all()
            self._after_selection()
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
        self.panel.copy_all.connect(self._copy_text_and_close)
        self.panel.copy_selection.connect(self._copy_text_and_close)
        self.panel.closed.connect(self.close_panel)
        self.panel.retry.connect(self._retry)
        self.panel.selection_changed.connect(self._on_panel_selection)
        self.copy_chip = QPushButton("Copiar", self.ov)
        self.copy_chip.setStyleSheet(CHIP_STYLE)
        self.copy_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copy_chip.clicked.connect(self._chip_copy)
        self.copy_chip.hide()

    def _measure(self):
        from PySide6.QtGui import QFont, QFontMetricsF

        fm = QFontMetricsF(QFont())
        return fm.horizontalAdvance

    def _open_panel(self) -> None:
        self.tool = None
        self.side.set_tool(None)
        self.side.set_tools_enabled(False)
        self.layout = TextLayout(self._ocr_blocks or [], measure=self._measure())
        self._anchor = None
        self.copy_chip.hide()
        self.panel.show_text(self.layout.text)
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
            self.copy_chip.hide()
        self._anchor = None
        self.side.set_tools_enabled(True)
        self.ov.setFocus()
        self.ov.update()

    def _sync_panel(self) -> None:
        if self.panel is not None and self.layout is not None:
            self.panel.set_selection(*self.layout.selection)

    def _on_panel_selection(self, a: int, b: int) -> None:
        if self.layout is None:
            return
        self.layout.select(a, b)
        self.copy_chip.hide()
        self.ov.update()

    def _text_mode_move(self, pos: QPointF) -> None:
        if self.layout is None or self._anchor is None:
            return
        pt = self.to_image(pos)
        self.layout.select(self._anchor, self.layout.position_at(pt.x, pt.y))
        self._sync_panel()
        self.ov.update()

    def _text_mode_release(self, pos: QPointF) -> None:
        if self.layout is None or self._anchor is None:
            return
        self._text_mode_move(pos)
        self._anchor = None
        self._after_selection()

    def double_click(self, pos: QPointF) -> bool:
        if not self.text_mode or self.layout is None or not self.ov.sel.contains(pos.toPoint()):
            return False
        pt = self.to_image(pos)
        a, b = self.layout.word_at(self.layout.position_at(pt.x, pt.y))
        self.layout.select(a, b)
        self._anchor = None
        self._after_selection()
        return True

    def _after_selection(self) -> None:
        self._sync_panel()
        rects = self.layout.selection_rects()
        if rects:
            x0, _, x1, y1 = rects[-1]
            r = self._local_rect(x0, y1, x1, y1)
            self.copy_chip.setText("Copiar")
            self.copy_chip.adjustSize()
            x = min(max(r.right() - self.copy_chip.width(), self.ov.sel.x()), self.ov.width() - self.copy_chip.width())
            y = r.bottom() + 8
            if y + self.copy_chip.height() > self.ov.height():
                top = self._local_rect(*rects[0])
                y = top.top() - self.copy_chip.height() - 8
            self.copy_chip.move(max(0, x), max(0, y))
            self.copy_chip.show()
            self.copy_chip.raise_()
        else:
            self.copy_chip.hide()
        self.ov.update()

    def _chip_copy(self) -> None:
        self._copy_selected_text()

    def _copy_selected_text(self) -> None:
        if self.layout is not None and self.layout.has_selection():
            self._copy_text_and_close(self.layout.selected_text())

    def _copy_text_and_close(self, text: str) -> None:
        """Copiou o texto: a captura já cumpriu o papel, então fecha tudo (como Copiar imagem)."""
        if not text:
            return
        copy_text(text)
        self.close()

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
