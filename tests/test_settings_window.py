from PySide6.QtWidgets import QLabel

from parzprint.settings import Settings
from parzprint.settings_window import SettingsWindow


def test_settings_window_hides_ocr_engine(qapp):
    win = SettingsWindow(Settings())
    texts = [w.text() for w in win.findChildren(QLabel)]
    assert not any("OCR" in t for t in texts)
    assert win.current().ocr_engine == "indra"
    win.close()


def test_settings_window_recording_fields(qapp, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    win = SettingsWindow(Settings())
    win.rec_resolution.setCurrentIndex(win.rec_resolution.findData("720"))
    win.rec_quality.setCurrentIndex(win.rec_quality.findData("leve"))
    win.rec_fps.setCurrentIndex(win.rec_fps.findData(15))
    win.rec_compress.setChecked(False)
    win.rec_countdown.setChecked(False)
    win.video_dir.setText("D:/Videos")
    s = win.current()
    assert (s.rec_resolution, s.rec_quality, s.rec_fps) == ("720", "leve", 15)
    assert s.rec_compress is False and s.rec_countdown is False and s.video_dir == "D:/Videos"
    assert s.ptt_hotkey == "Ctrl+Alt+Space"
    win.close()


def test_settings_window_hides_recording_off_windows(qapp, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "platform", "linux")
    win = SettingsWindow(Settings())
    assert win.recording_box is None
    assert win.current().rec_quality == "media"
    win.close()


def test_settings_window_translator_fields(qapp):
    win = SettingsWindow(Settings())
    assert win.translate_hotkey.value == Settings().translate_hotkey
    assert win.translate_grab_selection.text() == "Pegar o texto selecionado"
    assert win.translate_grab_selection.isChecked()
    texts = [w.text() for w in win.findChildren(QLabel)]
    assert "Para traduzir, o texto é enviado ao Google Tradutor. Nada sai do computador sem você pedir." in texts
    win.translate_hotkey.value = "Ctrl+Alt+U"
    win.translate_grab_selection.setChecked(False)
    s = win.current()
    assert s.translate_hotkey == "Ctrl+Alt+U" and s.translate_grab_selection is False
    win.close()


def test_settings_window_refuses_repeated_hotkey(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    win = SettingsWindow(Settings())
    got = []
    win.saved.connect(got.append)
    win.translate_hotkey.value = win.hotkey.value
    win._save()
    assert got == [] and warned and "repetido" in warned[0]
    assert win.isVisible() or win.result() == 0
    win.close()


def test_settings_window_translator_hotkey_on_wayland(qapp, monkeypatch):
    import parzprint.settings_window as sw

    monkeypatch.setattr(sw, "is_wayland", lambda: True)
    win = SettingsWindow(Settings())
    assert not win.translate_hotkey.isEnabled()
    texts = [w.text() for w in win.translate_box.findChildren(QLabel)]
    assert any("parzprint --translate" in t for t in texts)
    win.close()
