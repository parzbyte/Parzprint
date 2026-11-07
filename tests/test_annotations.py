from PIL import Image

from parzprint.annotations import (
    DEFAULT_COLOR, PALETTE, AnnotationStack, Arrow, Line, Marker, Pencil, Point, Rect, Text, render,
)


def test_palette_and_default():
    assert PALETTE == ["#E53935", "#FDD835", "#43A047", "#1E88E5", "#000000", "#FFFFFF"]
    assert DEFAULT_COLOR == "#E53935"


def test_add_and_undo():
    s = AnnotationStack()
    s.add(Line(Point(0, 0), Point(5, 5), "#E53935"))
    assert len(s) == 1
    assert isinstance(s.undo(), Line)
    assert len(s) == 0
    assert s.undo() is None


def test_empty_text_annotation_is_dropped():
    s = AnnotationStack()
    s.add(Text(Point(1, 1), "   ", "#000000"))
    assert len(s) == 0
    s.add(Text(Point(1, 1), "oi", "#000000"))
    assert len(s) == 1


def test_render_rect_paints_border_pixel_and_keeps_original():
    img = Image.new("RGB", (50, 50), "white")
    out = render(img, [Rect(Point(10, 10), Point(30, 30), "#E53935", width=1)])
    assert out.getpixel((10, 20))[:3] == (229, 57, 53)
    assert out.getpixel((20, 20))[:3] == (255, 255, 255)
    assert img.getpixel((10, 20)) == (255, 255, 255)


def test_render_rect_accepts_reversed_corners():
    out = render(Image.new("RGB", (50, 50), "white"), [Rect(Point(30, 30), Point(10, 10), "#000000", width=1)])
    assert out.getpixel((10, 20))[:3] == (0, 0, 0)


def test_render_arrow_paints_head():
    out = render(Image.new("RGB", (60, 30), "white"), [Arrow(Point(5, 15), Point(50, 15), "#000000", width=1)])
    assert out.getpixel((48, 15))[:3] == (0, 0, 0)
    assert out.getpixel((40, 11))[:3] == (0, 0, 0)  # wing of the head, off the shaft


def test_render_pencil_and_line():
    out = render(
        Image.new("RGB", (40, 40), "white"),
        [Pencil([Point(2, 2), Point(2, 30)], "#000000"), Line(Point(10, 35), Point(35, 35), "#000000")],
    )
    assert out.getpixel((2, 15))[:3] == (0, 0, 0)
    assert out.getpixel((20, 35))[:3] == (0, 0, 0)


def test_render_marker_is_translucent():
    out = render(Image.new("RGB", (40, 40), "white"), [Marker([Point(5, 20), Point(35, 20)], "#1E88E5")])
    px = out.getpixel((20, 20))[:3]
    assert px != (255, 255, 255)
    assert px != (30, 136, 229)


def test_render_text_draws_something():
    out = render(Image.new("RGB", (120, 40), "white"), [Text(Point(5, 5), "Olá", "#000000", size=20)])
    assert any(out.getpixel((x, y))[:3] != (255, 255, 255) for x in range(120) for y in range(40))


def test_render_keeps_mode():
    img = Image.new("RGB", (10, 10), "white")
    assert render(img, []).mode == "RGB"
