from PySide6.QtWidgets import QLabel

from parzprint.settings import Settings
from parzprint.settings_window import SettingsWindow


def test_settings_window_hides_ocr_engine(qapp):
    win = SettingsWindow(Settings())
    texts = [w.text() for w in win.findChildren(QLabel)]
    assert not any("OCR" in t for t in texts)
    assert win.current().ocr_engine == "indra"
    win.close()
