from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, QRect, Signal

import parzprint.app as app_mod
from parzprint.hotkey import HotkeyError
from parzprint.settings import Settings
from parzprint.translate.grab import Grabbed
from parzprint.tray import Tray
from tests.conftest import wait_until


MASKS = []


class FakeQApp:
    def __init__(self):
        self.quit_called = False

    def setQuitOnLastWindowClosed(self, v):
        pass

    def setWindowIcon(self, icon):
        pass

    def quit(self):
        self.quit_called = True


class FakeInstance(QObject):
    message_received = Signal(str)


class FakeHotkey:
    made = []
    fail = set()

    def __init__(self, hotkey, cb):
        self.hotkey, self.cb = hotkey, cb
        self.started = self.stopped = False
        FakeHotkey.made.append(self)

    def start(self):
        if self.hotkey in FakeHotkey.fail:
            raise HotkeyError(f"ocupado {self.hotkey}")
        self.started = True

    def stop(self):
        self.stopped = True

    def rebind(self, hotkey):
        self.hotkey = hotkey


class FakeTranslator:
    made = []

    def __init__(self, *a, **k):
        self.shut = False
        FakeTranslator.made.append(self)

    def shutdown(self):
        self.shut = True


class FakeWindow:
    made = []

    def __init__(self, translator, settings, on_settings_changed):
        self.translator, self.settings, self.on_settings_changed = translator, settings, on_settings_changed
        self.opened = []
        FakeWindow.made.append(self)

    def open(self, text, anchor, auto):
        self.opened.append((text, anchor, auto))

    def close(self):
        self.closed = True


class FakeEditor(QObject):
    record_requested = Signal(object, object, object)
    translate_requested = Signal(str, QRect)
    made = []

    def __init__(self, *a, **k):
        super().__init__()
        FakeEditor.made.append(self)


@pytest.fixture
def env(qapp, monkeypatch):
    FakeHotkey.made, FakeHotkey.fail = [], set()
    FakeTranslator.made, FakeWindow.made, FakeEditor.made = [], [], []
    saved, notes, grabs = [], [], []
    monkeypatch.setattr(app_mod, "load_settings", lambda: Settings())
    monkeypatch.setattr(app_mod, "save_settings", saved.append)
    monkeypatch.setattr(app_mod, "set_autostart", lambda on: None)
    monkeypatch.setattr(app_mod, "is_wayland", lambda: False)
    monkeypatch.setattr(app_mod, "GlobalHotkey", FakeHotkey)
    monkeypatch.setattr(app_mod, "GoogleTranslator", FakeTranslator)
    monkeypatch.setattr(app_mod, "TranslatorWindow", FakeWindow)
    monkeypatch.setattr(app_mod, "Editor", FakeEditor)
    monkeypatch.setattr(app_mod, "WinBackend", lambda: "win")
    monkeypatch.setattr(app_mod, "QtBackend", lambda: "qt")
    MASKS.clear()
    monkeypatch.setattr(app_mod, "mask_alt_menu", lambda: MASKS.append(1))
    monkeypatch.setattr(Tray, "notify", lambda self, title, text: notes.append(text))
    result = {"grabbed": Grabbed("", "none")}

    def fake_grab(backend, grab_selection):
        grabs.append((backend, grab_selection))
        return result["grabbed"]

    monkeypatch.setattr(app_mod, "grab", fake_grab)
    made = []

    def build():
        made.append(app_mod.App(FakeQApp(), FakeInstance()))
        return made[-1]

    yield build, result, saved, notes, grabs
    for a in made:
        a.tray.hide()
        a.deleteLater()


def _press(app, result, grabbed):
    result["grabbed"] = grabbed
    app.translate_shortcut()
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)
    return FakeWindow.made[0].opened[-1]


def test_selection_translates_at_once(env):
    build, result, *_ = env
    app = build()
    text, anchor, auto = _press(app, result, Grabbed("hello", "selection"))
    assert (text, auto) == ("hello", True)
    assert anchor.size().width() == 1 and anchor.size().height() == 1


def test_clipboard_waits_for_enter(env):
    build, result, *_ = env
    app = build()
    text, _, auto = _press(app, result, Grabbed("old", "clipboard"))
    assert (text, auto) == ("old", False)


def test_grab_uses_platform_backend_and_setting(env, monkeypatch):
    import sys

    build, result, _, _, grabs = env
    app = build()
    app.settings = replace(app.settings, translate_grab_selection=False)
    _press(app, result, Grabbed("x", "clipboard"))
    expected = "win" if sys.platform == "win32" else "qt"
    assert grabs == [(expected, False)]


def test_window_created_only_on_first_use(env):
    build, result, *_ = env
    app = build()
    assert FakeWindow.made == [] and FakeTranslator.made == []
    app.open_translator("a", QRect(0, 0, 1, 1), auto=False)
    app.open_translator("b", QRect(0, 0, 1, 1), auto=False)
    assert len(FakeWindow.made) == 1 and len(FakeTranslator.made) == 1
    assert FakeWindow.made[0].translator is FakeTranslator.made[0]


def test_tray_item_opens_empty(env):
    build, *_ = env
    app = build()
    app.tray.translate_requested.emit()
    assert FakeWindow.made[0].opened[-1][0] == "" and FakeWindow.made[0].opened[-1][2] is False


def test_editor_translate_opens_on_area(env):
    build, *_ = env
    app = build()
    app._on_region(None, None)
    area = QRect(10, 20, 300, 80)
    FakeEditor.made[0].translate_requested.emit("texto lido", area)
    assert FakeWindow.made[0].opened == [("texto lido", area, True)]


def test_message_translate_runs_shortcut(env):
    build, result, *_ = env
    app = build()
    result["grabbed"] = Grabbed("oi", "selection")
    app.handle_message("translate")
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)


def test_window_settings_are_saved(env):
    build, _, saved, *_ = env
    app = build()
    app.open_translator("", QRect(0, 0, 1, 1), auto=False)
    new = replace(app.settings, translate_target="en")
    FakeWindow.made[0].on_settings_changed(new)
    assert app.settings == new and app.recorder.settings is app.settings and saved == [app.settings]


def test_apply_settings_updates_window_and_rebinds(env):
    build, _, saved, *_ = env
    app = build()
    app.open_translator("", QRect(0, 0, 1, 1), auto=False)
    new = replace(app.settings, translate_hotkey="Ctrl+Alt+U")
    app.apply_settings(new)
    assert FakeWindow.made[0].settings is app.settings and app.settings == new
    assert app.translate_hotkey.hotkey == "Ctrl+Alt+U"


def test_two_independent_hotkeys(env):
    build, *_ = env
    app = build()
    assert [h.hotkey for h in FakeHotkey.made] == [app.settings.hotkey, app.settings.translate_hotkey]
    assert app.hotkey.started and app.translate_hotkey.started


def test_translate_hotkey_failure_keeps_capture(env):
    build, _, _, notes, _ = env
    FakeHotkey.fail = {Settings().translate_hotkey}
    app = build()
    assert app.hotkey is not None and app.hotkey.started
    assert app.translate_hotkey is None
    assert any(n.startswith("Atalho do tradutor indisponível:") for n in notes)


def test_capture_hotkey_failure_keeps_translate(env):
    build, _, _, notes, _ = env
    FakeHotkey.fail = {Settings().hotkey}
    app = build()
    assert app.hotkey is None and app.translate_hotkey is not None and app.translate_hotkey.started


def test_translate_hotkey_press_reaches_gui(env):
    build, result, *_ = env
    app = build()
    result["grabbed"] = Grabbed("oi", "selection")
    app.translate_hotkey.cb()
    assert MASKS == [1]
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)


def test_quit_shuts_translator_and_hotkeys(env):
    build, *_ = env
    app = build()
    app.open_translator("", QRect(0, 0, 1, 1), auto=False)
    hk, thk = app.hotkey, app.translate_hotkey
    app.quit()
    assert FakeTranslator.made[0].shut and FakeWindow.made[0].closed and hk.stopped and thk.stopped


def test_quit_without_translator(env):
    build, *_ = env
    app = build()
    app.quit()
    assert FakeTranslator.made == []


def test_settings_window_save_keeps_translator_changes(env):
    build, *_ = env
    app = build()
    app.open_settings()
    win = app.settings_window
    app.open_translator("", QRect(0, 0, 1, 1), auto=False)
    tw = FakeWindow.made[0]
    tw.on_settings_changed(replace(app.settings, translate_target="en", translate_recent=["en"], translate_pinned=True))
    win.autostart.setChecked(not app.settings.autostart)
    app.apply_settings(win.current())
    s = app.settings
    assert (s.translate_target, s.translate_recent, s.translate_pinned) == ("en", ["en"], True)
    assert s.autostart == win.autostart.isChecked()
    assert tw.settings.translate_target == "en"
    win.close()


def test_grab_failure_opens_empty_and_logs(env, monkeypatch, caplog):
    build, *_ = env
    app = build()

    def boom(backend, grab_selection):
        raise RuntimeError("falhou")

    monkeypatch.setattr(app_mod, "grab", boom)
    app.translate_shortcut()
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)
    assert FakeWindow.made[0].opened[-1][0] == "" and FakeWindow.made[0].opened[-1][2] is False
    assert any("falhou" in (r.exc_text or str(r.exc_info)) for r in caplog.records)


def test_grab_failure_off_windows(env, monkeypatch):
    import sys

    build, *_ = env
    app = build()
    monkeypatch.setattr(sys, "platform", "linux")

    def boom(backend, grab_selection):
        raise RuntimeError("falhou")

    monkeypatch.setattr(app_mod, "grab", boom)
    app.translate_shortcut()
    assert FakeWindow.made[0].opened[-1][0] == ""


def test_second_press_while_grabbing_is_ignored(env, monkeypatch):
    import threading

    build, result, _, _, grabs = env
    app = build()
    gate = threading.Event()

    def slow(backend, grab_selection):
        grabs.append(backend)
        gate.wait(3)
        return Grabbed("oi", "selection")

    monkeypatch.setattr(app_mod, "grab", slow)
    monkeypatch.setattr(app_mod.sys, "platform", "win32")
    app.translate_shortcut()
    app.translate_shortcut()
    gate.set()
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)
    assert len(grabs) == 1 and len(FakeWindow.made[0].opened) == 1
    app.translate_shortcut()
    assert wait_until(lambda: len(FakeWindow.made[0].opened) == 2)


def test_translator_save_keeps_recording_mic(env):
    build, _, saved, *_ = env
    app = build()
    app.open_translator("", QRect(0, 0, 1, 1), auto=False)
    tw = FakeWindow.made[0]
    stale = tw.settings
    app._save_from_recording(replace(app.settings, mic_device="X"))
    assert tw.settings.mic_device == "X"
    tw.on_settings_changed(replace(stale, translate_target="en"))
    assert (saved[-1].mic_device, saved[-1].translate_target) == ("X", "en")
    assert app.settings == saved[-1] and app.recorder.settings == saved[-1] and tw.settings == saved[-1]


def test_mask_failure_still_opens_and_logs(env, monkeypatch, caplog):
    build, result, *_ = env
    app = build()

    def boom():
        raise RuntimeError("máscara falhou")

    monkeypatch.setattr(app_mod, "mask_alt_menu", boom)
    result["grabbed"] = Grabbed("oi", "selection")
    app.translate_hotkey.cb()
    assert wait_until(lambda: FakeWindow.made and FakeWindow.made[0].opened)
    assert any("máscara falhou" in (r.exc_text or str(r.exc_info)) for r in caplog.records)


def test_saved_conflict_skips_translate_hotkey(env, monkeypatch):
    build, _, _, notes, _ = env
    monkeypatch.setattr(app_mod, "load_settings", lambda: Settings(translate_hotkey=Settings().hotkey))
    app = build()
    assert app.hotkey is not None and app.hotkey.started
    assert app.translate_hotkey is None
    assert [h.hotkey for h in FakeHotkey.made] == [app.settings.hotkey]
    assert "O atalho do tradutor é igual a outro atalho. Troque em Configurações." in notes


def test_other_conflict_keeps_translate_hotkey(env, monkeypatch):
    build, _, _, notes, _ = env
    monkeypatch.setattr(app_mod, "load_settings", lambda: Settings(ptt_hotkey=Settings().hotkey))
    app = build()
    assert app.translate_hotkey is not None and app.translate_hotkey.started
    assert not any("tradutor é igual" in n for n in notes)


def test_quit_waits_for_grab_thread(env, monkeypatch):
    import threading

    build, *_ = env
    app = build()
    gate, done = threading.Event(), threading.Event()

    def slow(backend, grab_selection):
        gate.wait(3)
        done.set()
        return Grabbed("oi", "selection")

    monkeypatch.setattr(app_mod, "grab", slow)
    monkeypatch.setattr(app_mod.sys, "platform", "win32")
    app.translate_shortcut()
    assert wait_until(lambda: app._grab_pool.activeThreadCount() == 1)
    threading.Timer(0.2, gate.set).start()
    app.quit()
    assert done.is_set() and app._grab_pool.activeThreadCount() == 0


def test_grab_arriving_after_quit_is_ignored(env):
    build, *_ = env
    app = build()
    app.quit()
    app._on_grabbed("oi", "selection")
    assert FakeWindow.made == []
