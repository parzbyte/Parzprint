from pathlib import Path

from parzprint import brand
from parzprint.annotations import DEFAULT_COLOR, PALETTE

UI = ["toolbar.py", "textpanel.py", "editor.py", "overlay.py", "recording/recordbar.py", "recording/frame.py"]


def test_brand_colors():
    assert (brand.RED, brand.RED_DARK, brand.RED_LIGHT, brand.GRAPHITE, brand.GRAY) == (
        "#E11D2E", "#A3111F", "#FDE7E9", "#111111", "#E8E8E6")
    assert brand.SIGNATURE == "Parzprint, por Parzbyte"


def test_default_annotation_color_is_brand_red():
    assert DEFAULT_COLOR == brand.RED and PALETTE[0] == brand.RED


def test_ui_has_no_old_blue_accent():
    root = Path(__file__).resolve().parent.parent / "parzprint"
    for name in UI:
        text = (root / name).read_text(encoding="utf-8").upper()
        assert "1E88E5" not in text and "2196F3" not in text and "30, 136, 229" not in text, name


def test_widgets_use_brand_red(qapp):
    from parzprint import editor, overlay, textpanel, toolbar
    from parzprint.recording import frame, recordbar

    assert overlay.ACCENT.name().upper() == brand.RED
    assert frame.BORDER_COLOR.name().upper() == brand.RED
    for style in (toolbar.STYLE, textpanel.PANEL_STYLE, editor.CHIP_STYLE, recordbar.BAR_STYLE):
        assert brand.RED in style.upper() or brand.RED_RGB in style, style[:60]


def test_tray_tooltip_has_signature(qapp):
    from parzprint.tray import Tray

    t = Tray()
    t.set_hotkey_hint("Ctrl+Alt+S")
    assert t.toolTip() == "Parzprint, por Parzbyte (Ctrl+Alt+S)"
    t.set_hotkey_hint(None)
    assert t.toolTip() == "Parzprint, por Parzbyte"


def test_settings_window_shows_signature(qapp):
    from PySide6.QtWidgets import QLabel

    from parzprint.settings import Settings
    from parzprint.settings_window import SettingsWindow

    win = SettingsWindow(Settings())
    assert any(lbl.text() == brand.SIGNATURE for lbl in win.findChildren(QLabel))
    win.close()


def test_icon_is_brand_red():
    from PIL import Image

    icon = Image.open(Path(__file__).resolve().parent.parent / "parzprint" / "assets" / "icon.png").convert("RGB")
    assert icon.getpixel((30, 128)) == (225, 29, 46)
