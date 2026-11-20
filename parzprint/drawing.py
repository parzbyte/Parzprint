"""Desenho compartilhado entre o editor de print e a camada de desenho da gravação."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit

from .annotations import Annotation, Arrow, Line, Marker, Pencil, Point, Rect
from .toolbar import Tool

TEXT_SIZE = 20
# tamanho inicial de cada ferramenta (pixels lógicos; para Texto, tamanho da fonte)
DEFAULT_SIZES = {
    Tool.PENCIL: 3, Tool.LINE: 3, Tool.ARROW: 4, Tool.RECT: 3, Tool.MARKER: 16, Tool.TEXT: TEXT_SIZE,
}
SIZE_LIMITS = {Tool.MARKER: (6, 60), Tool.TEXT: (10, 72)}  # demais: 1 a 30
SIZE_STEPS = {Tool.MARKER: 2, Tool.TEXT: 2}  # demais: 1


def step_size(tool: Tool, size: int, delta: int) -> int:
    """Tamanho depois de um passo da roda do mouse (``delta`` > 0 aumenta), dentro dos limites."""
    lo, hi = SIZE_LIMITS.get(tool, (1, 30))
    step = SIZE_STEPS.get(tool, 1) * (1 if delta > 0 else -1)
    return max(lo, min(hi, size + step))


def new_shape(tool: Tool, pt: Point, color: str, width: int) -> Annotation | None:
    """Forma que começa em ``pt``. Texto não é forma de arrastar: devolve None."""
    if tool is Tool.PENCIL:
        return Pencil([pt], color, width)
    if tool is Tool.MARKER:
        return Marker([pt], color, width)
    if tool is Tool.LINE:
        return Line(pt, pt, color, width)
    if tool is Tool.ARROW:
        return Arrow(pt, pt, color, width)
    if tool is Tool.RECT:
        return Rect(pt, pt, color, width)
    return None


def extend_shape(shape: Annotation, pt: Point) -> None:
    if isinstance(shape, (Pencil, Marker)):
        shape.points.append(pt)
    else:
        shape.end = pt


def is_empty(shape: Annotation) -> bool:
    """Linha, seta ou retângulo sem arrastar não viram anotação."""
    return isinstance(shape, (Line, Arrow, Rect)) and shape.start == shape.end


class TextInput(QLineEdit):
    """Campo da ferramenta Texto: Enter confirma e Esc cancela, sem repassar a tecla
    para a janela de baixo (onde Enter copiaria a imagem e Esc fecharia a captura)."""

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
