"""Janela de seleção de área (uma por monitor) e a sessão de captura que as coordena."""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QRegion
from PySide6.QtWidgets import QWidget

from .capture import CaptureError, Monitor, grab_all
from .geometry import normalize_rect
from .qtutil import pil_to_qpixmap

HANDLE = 8
MIN_SIZE = 3
DIM = QColor(0, 0, 0, 128)
ACCENT = QColor("#1E88E5")


class Mode(Enum):
    IDLE = auto()
    DRAGGING = auto()
    SELECTED = auto()


# alças: (fração x, fração y)
_HANDLES = {
    "tl": (0, 0), "t": (0.5, 0), "tr": (1, 0),
    "l": (0, 0.5), "r": (1, 0.5),
    "bl": (0, 1), "b": (0.5, 1), "br": (1, 1),
}
_HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
}


class SelectionOverlay(QWidget):
    """Cobre um monitor com a foto escurecida; o usuário arrasta para escolher a área.

    Coordenadas internas são locais à janela, em pixels lógicos. Depois da primeira
    seleção, um ``editor`` (ver ``editor.py``) pode ser ligado para receber o mouse
    dentro da área e desenhar por cima.
    """

    selected = Signal(QRect)           # primeira seleção concluída (coordenadas globais)
    selection_changed = Signal(QRect)  # moveu ou redimensionou (coordenadas locais)
    cancelled = Signal()

    def __init__(self, monitor: Monitor):
        super().__init__(None)
        self.monitor = monitor
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setGeometry(monitor.x, monitor.y, monitor.width, monitor.height)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._background = pil_to_qpixmap(monitor.image, monitor.scale)
        self.mode = Mode.IDLE
        self.sel = QRect()
        self._anchor = QPoint()
        self._drag_kind: str | None = None  # "move" ou nome da alça
        self._drag_origin = QPoint()
        self._drag_start_sel = QRect()
        self.editor = None
        self.locked = False  # True depois da primeira seleção: não redesenha do zero

    # ---------- geometria ----------
    def selection_global(self) -> QRect:
        return self.sel.translated(self.monitor.x, self.monitor.y)

    def screen_rect(self) -> QRect:
        return QRect(0, 0, self.width(), self.height())

    def _handle_rects(self) -> dict[str, QRect]:
        s = self.sel
        out = {}
        for name, (fx, fy) in _HANDLES.items():
            cx = s.x() + round(fx * s.width())
            cy = s.y() + round(fy * s.height())
            out[name] = QRect(cx - HANDLE // 2, cy - HANDLE // 2, HANDLE, HANDLE)
        return out

    def handle_at(self, p: QPoint) -> str | None:
        if self.mode is not Mode.SELECTED or self._editor_busy():
            return None
        for name, r in self._handle_rects().items():
            if r.adjusted(-3, -3, 3, 3).contains(p):
                return name
        return None

    def _resized(self, kind: str, dx: int, dy: int) -> QRect:
        s = self._drag_start_sel
        left, top, right, bottom = s.x(), s.y(), s.x() + s.width(), s.y() + s.height()
        if "l" in kind:
            left += dx
        if "r" in kind:
            right += dx
        if kind.startswith("t"):
            top += dy
        if kind.startswith("b"):
            bottom += dy
        x, y, w, h = normalize_rect(left, top, right, bottom)
        return QRect(x, y, max(w, MIN_SIZE), max(h, MIN_SIZE)).intersected(self.screen_rect())

    def _editor_busy(self) -> bool:
        return self.editor is not None and self.editor.blocks_selection_change()

    # ---------- mouse ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton and not self._editor_busy():
            self.cancelled.emit()
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        p = e.position().toPoint()
        if self.mode is Mode.SELECTED:
            handle = self.handle_at(p)
            if handle:
                self._start_drag(handle, p)
                return
            if self.editor is not None and self.editor.press(e.position()):
                return
            if self.sel.contains(p) and not self._editor_busy():
                self._start_drag("move", p)
                return
            if self.locked:
                return
        self.mode = Mode.DRAGGING
        self._anchor = p
        self.sel = QRect(p, p)
        self.update()

    def _start_drag(self, kind: str, p: QPoint) -> None:
        self._drag_kind = kind
        self._drag_origin = p
        self._drag_start_sel = QRect(self.sel)

    def mouseMoveEvent(self, e):
        p = e.position().toPoint()
        if self.mode is Mode.DRAGGING:
            x, y, w, h = normalize_rect(self._anchor.x(), self._anchor.y(), p.x(), p.y())
            self.sel = QRect(x, y, w, h).intersected(self.screen_rect())
            self.update()
            return
        if self._drag_kind:
            dx, dy = p.x() - self._drag_origin.x(), p.y() - self._drag_origin.y()
            if self._drag_kind == "move":
                r = self._drag_start_sel.translated(dx, dy)
                r.moveLeft(max(0, min(r.x(), self.width() - r.width())))
                r.moveTop(max(0, min(r.y(), self.height() - r.height())))
                self.sel = r
            else:
                self.sel = self._resized(self._drag_kind, dx, dy)
            self.selection_changed.emit(QRect(self.sel))
            self.update()
            return
        if self.editor is not None and self.editor.move(e.position()):
            return
        self._update_cursor(p)

    def _update_cursor(self, p: QPoint) -> None:
        handle = self.handle_at(p)
        editor_cursor = self.editor.cursor_for(p) if self.editor is not None else None
        if handle:
            self.setCursor(_HANDLE_CURSORS[handle])
        elif editor_cursor is not None:
            self.setCursor(editor_cursor)
        elif self.mode is Mode.SELECTED and self.sel.contains(p):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.mode is Mode.DRAGGING:
            if self.sel.width() < MIN_SIZE or self.sel.height() < MIN_SIZE:
                self.mode = Mode.IDLE
                self.sel = QRect()
                self.update()
                return
            self.mode = Mode.SELECTED
            self.update()
            self.selected.emit(self.selection_global())
            return
        if self._drag_kind:
            self._drag_kind = None
            self.selection_changed.emit(QRect(self.sel))
            return
        if self.editor is not None:
            self.editor.release(e.position())

    def mouseDoubleClickEvent(self, e):
        if (
            e.button() == Qt.MouseButton.LeftButton
            and self.editor is not None
            and self.editor.double_click(e.position())
        ):
            return
        self.mousePressEvent(e)  # sem uso especial: vale como um clique normal

    def wheelEvent(self, e):
        if self.editor is not None and self.editor.wheel(e.angleDelta().y(), e.position()):
            e.accept()
            return
        super().wheelEvent(e)

    # ---------- teclado ----------
    def keyPressEvent(self, e):
        if self.editor is not None and self.editor.key(e):
            return
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(e)

    # ---------- pintura ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._background)
        dim = QRegion(self.rect())
        if not self.sel.isEmpty():
            dim = dim.subtracted(QRegion(self.sel))
        p.save()
        p.setClipRegion(dim)
        p.fillRect(self.rect(), DIM)
        p.restore()
        if self.sel.isEmpty():
            return
        if self.editor is not None:
            self.editor.paint(p)
        p.setPen(QPen(ACCENT, 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.sel.adjusted(0, 0, -1, -1))
        if self.mode is Mode.SELECTED and not self._editor_busy():
            p.setPen(QPen(Qt.GlobalColor.white, 1))
            p.setBrush(ACCENT)
            for r in self._handle_rects().values():
                p.drawRect(r)
        self._paint_size_label(p)

    def _paint_size_label(self, p: QPainter) -> None:
        s = self.monitor.scale
        text = f"{round(self.sel.width() * s)} × {round(self.sel.height() * s)}"
        font = QFont(self.font())
        font.setPointSize(9)
        p.setFont(font)
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 12, fm.height() + 6
        x, y = self.sel.x(), self.sel.y() - h - 4
        if y < 0:
            x, y = self.sel.x() + 4, self.sel.y() + 4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 180))
        p.drawRoundedRect(QRect(x, y, w, h), 4, 4)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, text)


class CaptureSession(QObject):
    """Fotografa os monitores, abre um overlay em cada um e coordena o fim da captura."""

    region_ready = Signal(object, QRect)  # (SelectionOverlay, seleção global)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, overlay_factory=SelectionOverlay, parent=None):
        super().__init__(parent)
        self._factory = overlay_factory
        self.overlays: list[SelectionOverlay] = []
        self.active: SelectionOverlay | None = None
        self._closed = False

    def start(self) -> bool:
        try:
            monitors = grab_all()
        except CaptureError as e:
            self.failed.emit(str(e))
            self.finished.emit()
            return False
        cursor = QCursor.pos()
        for m in monitors:
            ov = self._factory(m)
            ov.selected.connect(lambda rect, ov=ov: self._on_selected(ov, rect))
            ov.cancelled.connect(self.close)
            self.overlays.append(ov)
            ov.show()
            if QRect(m.x, m.y, m.width, m.height).contains(cursor):
                self.active = ov
        target = self.active or self.overlays[0]
        target.raise_()
        target.activateWindow()
        target.setFocus()
        return True

    def _on_selected(self, overlay: SelectionOverlay, rect: QRect) -> None:
        if overlay.locked:
            return
        self.active = overlay
        for ov in list(self.overlays):
            if ov is not overlay:
                ov.close()
        self.overlays = [overlay]
        overlay.locked = True
        overlay.activateWindow()
        overlay.setFocus()
        self.region_ready.emit(overlay, rect)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for ov in self.overlays:
            ov.close()
        self.overlays = []
        self.finished.emit()
