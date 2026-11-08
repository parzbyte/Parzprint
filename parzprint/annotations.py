"""Modelo das anotações (formas desenhadas sobre a captura) e sua renderização."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from PIL import Image

PALETTE = ["#E53935", "#FDD835", "#43A047", "#1E88E5", "#000000", "#FFFFFF"]
DEFAULT_COLOR = PALETTE[0]
MARKER_ALPHA = 102  # 40%


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class Pencil:
    points: list[Point]
    color: str
    width: int = 3


@dataclass
class Line:
    start: Point
    end: Point
    color: str
    width: int = 3


@dataclass
class Arrow:
    start: Point
    end: Point
    color: str
    width: int = 3


@dataclass
class Rect:
    start: Point
    end: Point
    color: str
    width: int = 3


@dataclass
class Marker:
    points: list[Point]
    color: str
    width: int = 18


@dataclass
class Text:
    position: Point
    text: str
    color: str
    size: int = 18


Annotation = Pencil | Line | Arrow | Rect | Marker | Text


@dataclass
class AnnotationStack:
    _items: list[Annotation] = field(default_factory=list)

    def add(self, a: Annotation) -> None:
        if isinstance(a, Text) and not a.text.strip():
            return
        self._items.append(a)

    def undo(self) -> Annotation | None:
        return self._items.pop() if self._items else None

    def items(self) -> list[Annotation]:
        return list(self._items)

    def translate(self, dx: float, dy: float) -> None:
        """Desloca todas as anotações (usado quando a origem do recorte muda)."""
        self._items = [translated(a, dx, dy) for a in self._items]

    def __len__(self) -> int:
        return len(self._items)


def _shift(p: Point, dx: float, dy: float) -> Point:
    return Point(p.x + dx, p.y + dy)


def translated(a: Annotation, dx: float, dy: float) -> Annotation:
    if isinstance(a, (Pencil, Marker)):
        return replace(a, points=[_shift(p, dx, dy) for p in a.points])
    if isinstance(a, Text):
        return replace(a, position=_shift(a.position, dx, dy))
    return replace(a, start=_shift(a.start, dx, dy), end=_shift(a.end, dx, dy))


def _qcolor(color: str, alpha: int = 255):
    from PySide6.QtGui import QColor

    c = QColor(color)
    c.setAlpha(alpha)
    return c


def _pen(color, width: float, cap=None):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPen

    pen = QPen(color, width)
    pen.setCapStyle(cap if cap is not None else Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _smooth_path(points: list[Point]):
    """Caminho suave pelos pontos (curvas entre os pontos médios)."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath

    path = QPainterPath(QPointF(points[0].x, points[0].y))
    if len(points) == 1:
        path.lineTo(QPointF(points[0].x + 0.01, points[0].y))
        return path
    for a, b in zip(points[1:-1], points[2:]):
        mid = QPointF((a.x + b.x) / 2, (a.y + b.y) / 2)
        path.quadTo(QPointF(a.x, a.y), mid)
    path.lineTo(QPointF(points[-1].x, points[-1].y))
    return path


def arrow_head_size(width: float) -> tuple[float, float]:
    """(comprimento, meia-largura) da ponta da seta; cresce com a espessura, como no Lightshot."""
    length = 8 + width * 4
    return length, length * 0.42


def _paint_arrow(p, a: Arrow) -> None:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QPolygonF

    color = _qcolor(a.color)
    dx, dy = a.end.x - a.start.x, a.end.y - a.start.y
    dist = math.hypot(dx, dy)
    if dist < 0.5:
        return
    ux, uy = dx / dist, dy / dist
    length, half = arrow_head_size(a.width)
    length = min(length, dist)
    half = min(half, length * 0.42 if length < arrow_head_size(a.width)[0] else half)
    base = QPointF(a.end.x - ux * length, a.end.y - uy * length)
    # a haste termina dentro da ponta, para não aparecer um degrau na base
    shaft_end = QPointF(a.end.x - ux * length * 0.6, a.end.y - uy * length * 0.6)
    p.setPen(_pen(color, a.width, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(a.start.x, a.start.y), shaft_end)
    left = QPointF(base.x() - uy * half, base.y() + ux * half)
    right = QPointF(base.x() + uy * half, base.y() - ux * half)
    p.setPen(_pen(color, 1))
    p.setBrush(color)
    p.drawPolygon(QPolygonF([QPointF(a.end.x, a.end.y), left, right]))
    p.setBrush(Qt.BrushStyle.NoBrush)


def paint_annotation(p, a: Annotation) -> None:
    """Desenha uma anotação com um QPainter (coordenadas da imagem recortada)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QFont

    p.setRenderHint(p.RenderHint.Antialiasing, True)
    p.setRenderHint(p.RenderHint.TextAntialiasing, True)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if isinstance(a, Marker):
        p.setPen(_pen(_qcolor(a.color, MARKER_ALPHA), a.width, Qt.PenCapStyle.SquareCap))
        p.drawPath(_smooth_path(a.points))
    elif isinstance(a, Pencil):
        p.setPen(_pen(_qcolor(a.color), a.width))
        p.drawPath(_smooth_path(a.points))
    elif isinstance(a, Line):
        p.setPen(_pen(_qcolor(a.color), a.width))
        p.drawLine(QPointF(a.start.x, a.start.y), QPointF(a.end.x, a.end.y))
    elif isinstance(a, Arrow):
        _paint_arrow(p, a)
    elif isinstance(a, Rect):
        x0, x1 = sorted((a.start.x, a.end.x))
        y0, y1 = sorted((a.start.y, a.end.y))
        pen = _pen(_qcolor(a.color), a.width, Qt.PenCapStyle.SquareCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    elif isinstance(a, Text):
        f = QFont()
        f.setPixelSize(max(1, round(a.size)))
        p.setFont(f)
        p.setPen(_qcolor(a.color))
        ascent = p.fontMetrics().ascent()
        for i, line in enumerate(a.text.split("\n")):
            p.drawText(QPointF(a.position.x, a.position.y + ascent + i * p.fontMetrics().lineSpacing()), line)


def render(image: Image.Image, items: list[Annotation]) -> Image.Image:
    """Devolve uma cópia de ``image`` com as anotações desenhadas por cima (suavizadas)."""
    if not items:
        return image.copy()
    from PySide6.QtGui import QPainter

    from .qtutil import pil_to_qimage, qimage_to_pil

    mode = image.mode
    q = pil_to_qimage(image)
    p = QPainter(q)
    for a in items:
        paint_annotation(p, a)
    p.end()
    out = qimage_to_pil(q)
    return out if mode == "RGBA" else out.convert(mode)
