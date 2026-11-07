"""Modelo das anotações (formas desenhadas sobre a captura) e sua renderização."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

PALETTE = ["#E53935", "#FDD835", "#43A047", "#1E88E5", "#000000", "#FFFFFF"]
DEFAULT_COLOR = PALETTE[0]
MARKER_ALPHA = 102  # 40%
ARROW_HEAD = 12


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

    def __len__(self) -> int:
        return len(self._items)


_FONT_CANDIDATES = (
    ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    if sys.platform == "win32"
    else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
)


@lru_cache(maxsize=16)
def font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _xy(points: list[Point]) -> list[tuple[float, float]]:
    return [(p.x, p.y) for p in points]


def _rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(color)[:3]
    return (r, g, b, alpha)


def _polyline(draw: ImageDraw.ImageDraw, pts: list[Point], fill, width: int) -> None:
    if len(pts) == 1:
        p = pts[0]
        r = width / 2
        draw.ellipse([p.x - r, p.y - r, p.x + r, p.y + r], fill=fill)
        return
    draw.line(_xy(pts), fill=fill, width=width, joint="curve")


def _arrow(draw: ImageDraw.ImageDraw, a: Arrow) -> None:
    fill = _rgba(a.color)
    angle = math.atan2(a.end.y - a.start.y, a.end.x - a.start.x)
    head = ARROW_HEAD + a.width * 2
    base = Point(a.end.x - head * 0.8 * math.cos(angle), a.end.y - head * 0.8 * math.sin(angle))
    draw.line([(a.start.x, a.start.y), (base.x, base.y)], fill=fill, width=a.width)
    left = (a.end.x - head * math.cos(angle - math.pi / 7), a.end.y - head * math.sin(angle - math.pi / 7))
    right = (a.end.x - head * math.cos(angle + math.pi / 7), a.end.y - head * math.sin(angle + math.pi / 7))
    draw.polygon([(a.end.x, a.end.y), left, right], fill=fill)


def render(image: Image.Image, items: list[Annotation]) -> Image.Image:
    """Devolve uma cópia de ``image`` com as anotações desenhadas por cima."""
    mode = image.mode
    out = image.convert("RGBA")
    for a in items:
        if isinstance(a, Marker):
            layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
            _polyline(ImageDraw.Draw(layer), a.points, _rgba(a.color, MARKER_ALPHA), a.width)
            out = Image.alpha_composite(out, layer)
            continue
        draw = ImageDraw.Draw(out)
        if isinstance(a, Pencil):
            _polyline(draw, a.points, _rgba(a.color), a.width)
        elif isinstance(a, Line):
            draw.line([(a.start.x, a.start.y), (a.end.x, a.end.y)], fill=_rgba(a.color), width=a.width)
        elif isinstance(a, Arrow):
            _arrow(draw, a)
        elif isinstance(a, Rect):
            x0, x1 = sorted((a.start.x, a.end.x))
            y0, y1 = sorted((a.start.y, a.end.y))
            draw.rectangle([x0, y0, x1, y1], outline=_rgba(a.color), width=a.width)
        elif isinstance(a, Text):
            draw.text((a.position.x, a.position.y), a.text, fill=_rgba(a.color), font=font(a.size))
    return out if mode == "RGBA" else out.convert(mode)
