from PIL import Image

from parzprint.annotations import (
    DEFAULT_COLOR, PALETTE, AnnotationStack, Arrow, Line, Marker, Pencil, Point, Rect, Text, render,
)


def test_palette_and_default():
    assert PALETTE == ["#E11D2E", "#FDD835", "#43A047", "#1565C0", "#000000", "#FFFFFF"]
    assert DEFAULT_COLOR == "#E11D2E"


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


def near(px, rgb, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], rgb))


def dark_box(img, threshold=128):
    """Retângulo (x0, y0, x1, y1) dos pixels escuros."""
    xs, ys = [], []
    for y in range(img.height):
        for x in range(img.width):
            if sum(img.getpixel((x, y))[:3]) / 3 < threshold:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def test_render_rect_paints_border_and_keeps_original():
    img = Image.new("RGB", (50, 50), "white")
    out = render(img, [Rect(Point(10, 10), Point(30, 30), "#E53935", width=3)])
    assert near(out.getpixel((10, 20)), (229, 57, 53))
    assert out.getpixel((20, 20))[:3] == (255, 255, 255)
    assert img.getpixel((10, 20)) == (255, 255, 255)


def test_render_rect_accepts_reversed_corners():
    out = render(Image.new("RGB", (50, 50), "white"), [Rect(Point(30, 30), Point(10, 10), "#000000", width=3)])
    assert near(out.getpixel((10, 20)), (0, 0, 0))


def test_render_is_antialiased():
    out = render(Image.new("RGB", (60, 60), "white"), [Line(Point(5, 8), Point(55, 50), "#000000", width=3)])
    grays = {out.getpixel((x, y))[0] for x in range(60) for y in range(60)}
    assert any(30 < g < 225 for g in grays)  # bordas suavizadas, não só preto e branco


def test_render_arrow_paints_shaft_and_head():
    out = render(Image.new("RGB", (100, 40), "white"), [Arrow(Point(5, 20), Point(90, 20), "#000000", width=3)])
    assert near(out.getpixel((30, 20)), (0, 0, 0))  # haste
    assert near(out.getpixel((86, 20)), (0, 0, 0))  # ponta
    x0, y0, x1, y1 = dark_box(out)
    assert y1 - y0 >= 10  # a cabeça é bem mais larga que a haste
    assert x1 <= 91  # não passa da ponta


def test_arrow_head_grows_with_width():
    def head_height(w):
        out = render(Image.new("RGB", (200, 120), "white"), [Arrow(Point(10, 60), Point(180, 60), "#000000", width=w)])
        _, y0, _, y1 = dark_box(out)
        return y1 - y0

    assert head_height(8) > head_height(2) * 2


def test_render_pencil_and_line():
    out = render(
        Image.new("RGB", (40, 40), "white"),
        [Pencil([Point(2, 2), Point(2, 30)], "#000000"), Line(Point(10, 35), Point(35, 35), "#000000")],
    )
    assert near(out.getpixel((2, 15)), (0, 0, 0))
    assert near(out.getpixel((20, 35)), (0, 0, 0))


def test_render_marker_is_translucent_and_uniform():
    out = render(
        Image.new("RGB", (60, 40), "white"),
        [Marker([Point(5, 20), Point(30, 20), Point(30, 21), Point(55, 20)], "#1E88E5")],
    )
    a, b = out.getpixel((15, 20))[:3], out.getpixel((30, 20))[:3]
    assert a != (255, 255, 255) and a != (30, 136, 229)
    assert near(a, b, tol=6)  # sem escurecer onde o traço se sobrepõe


def test_render_text_draws_something():
    out = render(Image.new("RGB", (120, 40), "white"), [Text(Point(5, 5), "Olá", "#000000", size=20)])
    assert any(out.getpixel((x, y))[:3] != (255, 255, 255) for x in range(120) for y in range(40))


def test_render_keeps_mode():
    img = Image.new("RGB", (10, 10), "white")
    assert render(img, []).mode == "RGB"


def test_stack_translate_moves_every_kind():
    from parzprint.annotations import Line, Marker, Text

    s = AnnotationStack()
    s.add(Rect(Point(0, 0), Point(2, 2), "#000000"))
    s.add(Marker([Point(1, 1)], "#000000"))
    s.add(Text(Point(3, 3), "a", "#000000"))
    s.add(Line(Point(0, 1), Point(1, 0), "#000000"))
    s.translate(10, -1)
    r, m, t, ln = s.items()
    assert (r.start, r.end) == (Point(10, -1), Point(12, 1))
    assert m.points == [Point(11, 0)]
    assert t.position == Point(13, 2)
    assert (ln.start, ln.end) == (Point(10, 0), Point(11, -1))
