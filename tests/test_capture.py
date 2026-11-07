import pytest
from PIL import Image

from parzprint.capture import CaptureError, Monitor, crop, grab_all, monitor_for_point


def _img(w=100, h=100):
    return Image.new("RGB", (w, h), "white")


def test_monitor_for_point():
    m = [Monitor(1, 0, 0, 100, 100, _img()), Monitor(2, 100, 0, 100, 100, _img())]
    assert monitor_for_point(m, 150, 50).index == 2
    assert monitor_for_point(m, 0, 0).index == 1
    assert monitor_for_point(m, 99, 99).index == 1
    assert monitor_for_point(m, 500, 50) is None


def test_monitor_for_point_negative_origin():
    m = [Monitor(1, -1920, 0, 1920, 1080, _img(10, 10))]
    assert monitor_for_point(m, -5, 10).index == 1


def test_crop_uses_monitor_offset():
    img = _img()
    img.putpixel((10, 10), (1, 2, 3))
    m = Monitor(2, 100, 0, 100, 100, img)
    out = crop(m, 110, 10, 5, 5)
    assert out.size == (5, 5)
    assert out.getpixel((0, 0)) == (1, 2, 3)


def test_crop_scales_when_image_is_physical_pixels():
    # monitor lógico 100x100 com escala 2: foto tem 200x200
    img = _img(200, 200)
    img.putpixel((20, 20), (9, 9, 9))
    m = Monitor(1, 0, 0, 100, 100, img)
    out = crop(m, 10, 10, 5, 5)
    assert out.size == (10, 10)
    assert out.getpixel((0, 0)) == (9, 9, 9)


def test_crop_clamps_to_monitor():
    m = Monitor(1, 0, 0, 100, 100, _img())
    assert crop(m, 90, 90, 50, 50).size == (10, 10)


def test_grab_all_wraps_errors(monkeypatch):
    import parzprint.capture as cap

    def boom():
        raise RuntimeError("sem display")

    monkeypatch.setattr(cap, "_grab_screens", boom)
    with pytest.raises(CaptureError, match="sem display"):
        grab_all()


def test_grab_all_empty_raises(monkeypatch):
    import parzprint.capture as cap

    monkeypatch.setattr(cap, "_grab_screens", lambda: [])
    with pytest.raises(CaptureError):
        grab_all()
