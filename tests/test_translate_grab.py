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


def test_copy_changes_sequence():
    b = FakeBackend(text="velho", copies_to="novo")
    assert grab(b, True) == Grabbed("novo", "selection")
    assert b.calls["send_copy"] == 1
    assert b.calls["wait"] == 1


def test_copy_no_change_falls_back_to_clipboard():
    b = FakeBackend(text="velho")
    t0 = time.monotonic()
    assert grab(b, True, wait_s=0.2) == Grabbed("velho", "clipboard")
    assert time.monotonic() - t0 <= 0.2 + 0.1


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
