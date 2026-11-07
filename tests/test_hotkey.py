import sys

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
