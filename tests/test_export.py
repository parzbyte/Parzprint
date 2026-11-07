from datetime import datetime

from PIL import Image

from parzprint.export import default_filename, save_image


def test_default_filename():
    now = datetime(2026, 11, 7, 19, 53, 2)
    assert default_filename(now, "PNG") == "Parzprint_2026-11-07_19-53-02.png"
    assert default_filename(now, "JPG") == "Parzprint_2026-11-07_19-53-02.jpg"


def test_save_png_and_jpg(tmp_path):
    img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    save_image(img, tmp_path / "a.png", "PNG")
    save_image(img, tmp_path / "a.jpg", "JPG")
    assert Image.open(tmp_path / "a.png").size == (4, 4)
    assert Image.open(tmp_path / "a.jpg").mode == "RGB"
    assert Image.open(tmp_path / "a.jpg").format == "JPEG"


def test_save_uses_extension_over_setting(tmp_path):
    img = Image.new("RGB", (4, 4), "white")
    save_image(img, tmp_path / "b.jpg", "PNG")
    assert Image.open(tmp_path / "b.jpg").format == "JPEG"


def test_save_creates_missing_folder(tmp_path):
    save_image(Image.new("RGB", (2, 2)), tmp_path / "novo" / "c.png", "PNG")
    assert (tmp_path / "novo" / "c.png").exists()


def test_save_appends_extension_when_missing(tmp_path):
    saved = save_image(Image.new("RGB", (2, 2)), tmp_path / "foto", "JPG")
    assert saved == tmp_path / "foto.jpg"
    assert Image.open(saved).format == "JPEG"
