import os
import sys
import time

import pytest

from parzprint.hotkey import (
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT, MOD_WIN, GlobalHotkey, HotkeyError, from_qt_key_event, is_wayland,
    to_pynput, to_win32,
)


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


@pytest.mark.skipif(sys.platform.startswith("linux"), reason="no Linux o pynput precisa de uma sessão X de verdade")
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


def test_to_win32():
    assert to_win32("Ctrl+Alt+S") == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x53)
    assert to_win32("Ctrl+Shift+S") == (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 0x53)
    assert to_win32("Win+Print") == (MOD_WIN | MOD_NOREPEAT, 0x2C)
    assert to_win32("Alt+F2") == (MOD_ALT | MOD_NOREPEAT, 0x71)
    assert to_win32("Ctrl+Alt+1") == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x31)
    assert to_win32("Ctrl+Del") == (MOD_CONTROL | MOD_NOREPEAT, 0x2E)


def test_to_win32_invalid_raises():
    with pytest.raises(HotkeyError):
        to_win32("Ctrl+")


@pytest.mark.skipif(sys.platform != "win32", reason="windows")
def test_windows_hotkey_is_exclusive():
    # registrado pelo Windows: uma segunda inscrição da mesma combinação é recusada,
    # o que mostra que a combinação passa a ser só deste programa
    a = GlobalHotkey("Ctrl+Alt+Shift+F10", lambda: None)
    a.start()
    try:
        b = GlobalHotkey("Ctrl+Alt+Shift+F10", lambda: None)
        with pytest.raises(HotkeyError, match="em uso"):
            b.start()
    finally:
        a.stop()
    c = GlobalHotkey("Ctrl+Alt+Shift+F10", lambda: None)
    c.start()  # depois do stop, a combinação fica livre de novo
    c.stop()


def test_listener_that_never_gets_ready_does_not_hang():
    import threading

    from parzprint.hotkey import _wait_ready

    class Stuck:
        def wait(self):
            threading.Event().wait()  # nunca fica pronto (thread do listener morreu)

        def is_alive(self):
            return False

    t = time.perf_counter()
    assert _wait_ready(Stuck(), 0.3) is False
    assert time.perf_counter() - t < 2

    class Ready:
        def wait(self):
            return None

        def is_alive(self):
            return True

    assert _wait_ready(Ready(), 0.3) is True


def test_windows_hotkey_callback_error_is_logged_and_loop_survives(caplog):
    from parzprint.hotkey import _WindowsHotkey

    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("callback quebrou")

    hk = _WindowsHotkey("Ctrl+Alt+S", boom)
    hk._fire()
    hk._fire()
    assert calls == [1, 1]
    assert any("callback quebrou" in (r.exc_text or str(r.exc_info)) for r in caplog.records)
