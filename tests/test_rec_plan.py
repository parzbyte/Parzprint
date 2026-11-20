from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRect

from parzprint.capture import Monitor
from parzprint.recording.plan import crop_box, output_size, temp_path, video_filename


def test_output_size_even_and_never_upscales():
    assert output_size(1920, 1080, "720") == (1280, 720)
    assert output_size(801, 601, "original") == (800, 600)
    assert output_size(640, 360, "1080") == (640, 360)
    assert output_size(1000, 1000, "480") == (480, 480)
    assert output_size(3, 3, "original") == (2, 2)


def test_output_size_keeps_aspect_when_reducing():
    w, h = output_size(2560, 1440, "1080")
    assert (w, h) == (1920, 1080)
    w, h = output_size(1366, 768, "480")
    assert h == 480 and w % 2 == 0 and abs(w / h - 1366 / 768) < 0.01


def test_crop_box_uses_monitor_offset_and_scale():
    m = Monitor(1, -1920, 0, 1920, 1080, Image.new("RGB", (2880, 1620)), dpr=1.5)
    assert crop_box(m, QRect(-1900, 100, 400, 300)) == (30, 150, 600, 450)
    assert crop_box(m, QRect(-100, 1000, 400, 300)) == (2730, 1500, 150, 120)


def test_video_names():
    assert video_filename(datetime(2026, 11, 20, 9, 5, 7)) == "Parzprint_2026-11-20_09-05-07.mp4"
    assert temp_path(Path("C:/v/a.mp4")) == Path("C:/v/a.gravando.mp4")


def test_output_size_reaches_target_height_exactly():
    assert output_size(801, 601, "480")[1] == 480
