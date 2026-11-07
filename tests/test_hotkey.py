import os
import sys
import time

import pytest

from parzprint.hotkey import GlobalHotkey, HotkeyError, from_qt_key_event, is_wayland, to_pynput


def test_to_pynput():
    assert to_pynput("Ctrl+Shift+S") == "<ctrl>+<shift>+s"
    assert to_pynput("Win+Print") == "<cmd>+<print_screen>"
    assert to_pynput("Alt+F2") == "<alt>+<f2>"
    assert to_pynput("Ctrl+Alt+1") == "<ctrl>+<alt>+1"


def test_to_pynput_invalid_raises():
    with pytest.raises(HotkeyError):
        to_pynput("Ctrl+")


def test_from_qt_key_event():
    assert from_qt_key_event({"Ctrl", "Shift"}, "S") == "Ctrl+Shift+S"
    assert from_qt_key_event({"Shift", "Ctrl"}, "s") == "Ctrl+Shift+S"
    assert from_qt_key_event({"Alt"}, "F2") == "Alt+F2"
    assert from_qt_key_event(set(), "S") is None
    assert from_qt_key_event({"Ctrl"}, "Ctrl") is None
    assert from_qt_key_event({"Ctrl"}, "") is None


def test_is_wayland(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert is_wayland({"XDG_SESSION_TYPE": "wayland"})
    assert is_wayland({"WAYLAND_DISPLAY": "wayland-0"})
    assert not is_wayland({"XDG_SESSION_TYPE": "x11"})
    monkeypatch.setattr(sys, "platform", "win32")
    assert not is_wayland({"XDG_SESSION_TYPE": "wayland"})


def test_global_hotkey_start_stop_rebind():
    hk = GlobalHotkey("Ctrl+Shift+F12", lambda: None)
    hk.start()
    try:
        hk.rebind("Ctrl+Alt+F11")
        assert hk.hotkey == "Ctrl+Alt+F11"
    finally:
        hk.stop()


def test_global_hotkey_rejects_invalid():
    with pytest.raises(HotkeyError):
        GlobalHotkey("Ctrl+", lambda: None).start()


def test_to_pynput_qt_key_names():
    assert to_pynput("Ctrl+Del") == "<ctrl>+<delete>"
    assert to_pynput("Ctrl+Ins") == "<ctrl>+<insert>"
    assert to_pynput("Alt+PgDown") == "<alt>+<page_down>"


@pytest.mark.skipif(not os.environ.get("PARZPRINT_KEYBOARD_TESTS"), reason="pressiona teclas reais no sistema")
def test_global_hotkey_fires_on_keys():
    import threading

    from pynput.keyboard import Controller, Key

    fired = threading.Event()
    hk = GlobalHotkey("Ctrl+Alt+F11", fired.set)
    hk.start()
    try:
        time.sleep(0.3)
        k = Controller()
        for x in (Key.ctrl, Key.alt, Key.f11):
            k.press(x)
        for x in (Key.f11, Key.alt, Key.ctrl):
            k.release(x)
        assert fired.wait(3)
    finally:
        hk.stop()
