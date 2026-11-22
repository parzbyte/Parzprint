import sys
import time

import pytest

from parzprint.translate.grab import Grabbed, WinBackend, grab


class FakeBackend:
    def __init__(self, text="", primary="__none__", copies_to=None):
        self.text = text
        self.primary = None if primary == "__none__" else primary
        self.copies_to = copies_to
        self.seq = 1
        self.calls = {"send_copy": 0, "wait": 0, "primary": 0}

    def sequence(self):
        return self.seq

    def send_copy(self):
        self.calls["send_copy"] += 1
        if self.copies_to is not None:
            self.seq += 1
            self.text = self.copies_to

    def wait_modifiers_released(self, timeout_s):
        self.calls["wait"] += 1

    def read_text(self):
        return self.text

    def read_primary(self):
        self.calls["primary"] += 1
        return self.primary


def test_primary_selection_wins():
    b = FakeBackend(text="velho", primary="x")
    assert grab(b, True) == Grabbed("x", "selection")
    assert b.calls["send_copy"] == 0
    assert b.calls["wait"] == 0


def test_copy_changes_sequence():
    b = FakeBackend(text="velho", copies_to="novo")
    assert grab(b, True) == Grabbed("novo", "selection")
    assert b.calls["send_copy"] == 1
    assert b.calls["wait"] == 1


def test_copy_no_change_falls_back_to_clipboard():
    b = FakeBackend(text="velho")
    t0 = time.monotonic()
    assert grab(b, True, wait_s=0.2) == Grabbed("velho", "clipboard")
    assert time.monotonic() - t0 <= 0.2 + 0.25


def test_send_copy_refused_falls_back_to_clipboard():
    b = FakeBackend(text="velho")

    def boom():
        raise OSError("SendInput recusado")

    b.send_copy = boom
    assert grab(b, True) == Grabbed("velho", "clipboard")


def test_sequence_changes_but_text_empty():
    b = FakeBackend(text="", copies_to="")
    assert grab(b, True) == Grabbed("", "none")


def test_empty_primary_goes_to_clipboard_without_copy():
    b = FakeBackend(text="velho", primary="")
    assert grab(b, True) == Grabbed("velho", "clipboard")
    assert b.calls["send_copy"] == 0


def test_option_off_never_copies():
    b = FakeBackend(text="velho", primary="x", copies_to="novo")
    assert grab(b, False) == Grabbed("velho", "clipboard")
    assert b.calls["send_copy"] == 0
    assert b.calls["primary"] == 0


def test_nothing():
    assert grab(FakeBackend(text=""), True, wait_s=0.05) == Grabbed("", "none")


def test_text_kept_intact():
    assert grab(FakeBackend(text="a\r\nb 😀"), False).text == "a\r\nb 😀"


@pytest.mark.skipif(sys.platform != "win32", reason="só Windows")
def test_win_backend_struct_and_sequence():
    import ctypes

    from parzprint.translate import grab as g

    assert ctypes.sizeof(g._INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    assert isinstance(WinBackend().sequence(), int)


class _FakeUser32:
    def __init__(self, held):
        self.held = set(held)
        self.sent = []

    def GetAsyncKeyState(self, vk):
        return 0x8000 if vk in self.held else 0

    def SendInput(self, count, arr, size):
        self.sent += [(arr[i].ki.wVk, arr[i].ki.dwFlags) for i in range(count)]
        return count


@pytest.mark.skipif(sys.platform != "win32", reason="só Windows")
def test_alt_solto_sozinho_nao_abre_o_menu_do_programa():
    """Com o Alt apertado, soltar o Ctrl e apertar uma tecla sem função evita que ele abra a barra de menus ao soltar."""
    backend = WinBackend()
    fake = backend._user32 = _FakeUser32(set())
    backend.mask_alt()
    assert fake.sent == []

    fake.held.update({0x11, 0x12})
    backend.mask_alt()
    assert [vk for vk, _ in fake.sent] == [0x11, 0xFF, 0xFF]
    assert [flags for _, flags in fake.sent] == [0x2, 0, 0x2]


@pytest.mark.parametrize("name", ["ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "mintty"])
def test_terminal_classes(name):
    from parzprint.translate.grab import is_terminal_class

    assert is_terminal_class(name)


@pytest.mark.parametrize("name", ["", "Notepad", "Chrome_WidgetWin_1", "consolewindowclassx"])
def test_other_classes_are_not_terminals(name):
    from parzprint.translate.grab import is_terminal_class

    assert not is_terminal_class(name)


@pytest.mark.skipif(sys.platform != "win32", reason="só Windows")
def test_no_ctrl_c_in_terminal():
    """Num terminal o Ctrl+C sem seleção mata o processo: não aperta nada e cai no texto copiado."""
    backend = WinBackend()
    fake = backend._user32 = _FakeUser32(set())
    backend.foreground_class = lambda: "CASCADIA_HOSTING_WINDOW_CLASS"
    with pytest.raises(OSError):
        backend.send_copy()
    assert fake.sent == []


@pytest.mark.skipif(sys.platform != "win32", reason="só Windows")
def test_ctrl_c_outside_terminal():
    backend = WinBackend()
    fake = backend._user32 = _FakeUser32(set())
    backend.foreground_class = lambda: "Notepad"
    backend.send_copy()
    assert [vk for vk, _ in fake.sent] == [0x11, 0x11, 0x43, 0x43, 0x11]



def test_mask_alt_menu_swallows_any_error(monkeypatch):
    from parzprint.translate import grab as g

    class Broken:
        def mask_alt(self):
            raise RuntimeError("quebrou")

    monkeypatch.setattr(g.sys, "platform", "win32")
    monkeypatch.setattr(g, "WinBackend", Broken)
    g.mask_alt_menu()
