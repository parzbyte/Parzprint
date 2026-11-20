from PySide6.QtGui import QColor, QImage

from parzprint.recording.video import FramePump, prepare_frame


def test_prepare_frame_crops_and_scales():
    img = QImage(400, 300, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    img.setPixelColor(100, 50, QColor("red"))
    img.setPixelColor(101, 50, QColor("red"))
    img.setPixelColor(100, 51, QColor("red"))
    img.setPixelColor(101, 51, QColor("red"))
    out = prepare_frame(img, (100, 50, 200, 100), (100, 50))
    assert (out.width(), out.height()) == (100, 50)
    assert out.pixelColor(0, 0).red() > 200 and out.pixelColor(0, 0).green() < 120


def test_prepare_frame_without_scaling_is_exact():
    img = QImage(50, 50, QImage.Format.Format_RGB32)
    img.fill(QColor("black"))
    img.setPixelColor(20, 30, QColor("blue"))
    out = prepare_frame(img, (10, 10, 30, 30), (30, 30))
    assert out.pixelColor(10, 20) == QColor("blue")


class Clock:
    def __init__(self):
        self.us = 0
        self.paused = False

    def now_us(self):
        return self.us


def test_pump_paces_to_fps(qapp):
    pump = FramePump(None, (0, 0, 10, 10), (10, 10), 30, draw_cursor=False)
    clock = Clock()
    pump.start(clock, capture=False)
    sent = []
    pump.frame_ready.connect(sent.append)
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    for i in range(60):  # 60 quadros em 1 s
        clock.us = i * 16_667
        pump.handle_image(img)
    assert 29 <= len(sent) <= 31
    assert sent[1].startTime() > sent[0].startTime()


def test_pump_ignores_frames_while_paused(qapp):
    pump = FramePump(None, (0, 0, 10, 10), (10, 10), 15, draw_cursor=False)
    clock = Clock()
    pump.start(clock, capture=False)
    sent = []
    pump.frame_ready.connect(sent.append)
    clock.paused = True
    pump.handle_image(QImage(10, 10, QImage.Format.Format_RGB32))
    assert sent == []


def test_cursor_failure_never_drops_frames(qapp, monkeypatch):
    import parzprint.recording.video as video

    def boom():
        raise OverflowError("handle")

    monkeypatch.setattr(video, "_cursor_image", boom)
    pump = FramePump(None, (0, 0, 10, 10), (10, 10), 30, draw_cursor=True)
    pump.screen = object()
    clock = Clock()
    pump.start(clock, capture=False)
    sent = []
    pump.frame_ready.connect(sent.append)
    pump.handle_image(QImage(10, 10, QImage.Format.Format_RGB32))
    assert len(sent) == 1


def test_win32_cursor_calls_declare_handle_types():
    import sys

    import pytest

    if sys.platform != "win32":
        pytest.skip("windows")
    import ctypes

    from parzprint.recording import video

    video._win32()
    for fn in ("DeleteObject", "SelectObject", "CreateDIBSection", "DeleteDC"):
        assert getattr(ctypes.windll.gdi32, fn).argtypes, fn
    assert ctypes.windll.user32.DrawIconEx.argtypes
