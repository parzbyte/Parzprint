"""Pega o texto a traduzir: a seleção atual ou, na falta dela, o que está na área de transferência."""

from __future__ import annotations

import ctypes
import sys
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Grabbed:
    text: str
    source: str  # "selection", "clipboard" ou "none"


class Backend(Protocol):
    def sequence(self) -> int: ...
    def send_copy(self) -> None: ...
    def wait_modifiers_released(self, timeout_s: float) -> None: ...
    def read_text(self) -> str: ...
    def read_primary(self) -> str | None:
        """None quando o sistema não tem seleção primária."""


def grab(backend: Backend, grab_selection: bool, wait_s: float = 0.3, poll_s: float = 0.02) -> Grabbed:
    if grab_selection:
        primary = backend.read_primary()
        if primary:
            return Grabbed(primary, "selection")
        if primary is None:
            backend.wait_modifiers_released(0.5)
            before = backend.sequence()
            try:
                backend.send_copy()
            except OSError:
                before = None
            deadline = time.monotonic() + wait_s
            while before is not None:
                if backend.sequence() != before:
                    text = backend.read_text()
                    if text:
                        return Grabbed(text, "selection")
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(poll_s)
    text = backend.read_text()
    if text:
        return Grabbed(text, "clipboard")
    return Grabbed("", "none")


# --- Windows -----------------------------------------------------------------------------

_DWORD, _WORD, _ULONG_PTR = ctypes.c_uint32, ctypes.c_uint16, ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", _WORD), ("wScan", _WORD), ("dwFlags", _DWORD), ("time", _DWORD),
                ("dwExtraInfo", _ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32), ("mouseData", _DWORD),
                ("dwFlags", _DWORD), ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", _DWORD), ("u", _INPUT_UNION)]


_INPUT_KEYBOARD, _KEYEVENTF_KEYUP = 1, 0x2
_VK_CONTROL, _VK_SHIFT, _VK_MENU, _VK_LWIN, _VK_RWIN, _VK_C = 0x11, 0x10, 0x12, 0x5B, 0x5C, 0x43
_CF_UNICODETEXT = 13


class WinBackend:
    """Windows via ctypes. Pode rodar fora da thread da interface."""

    def __init__(self) -> None:
        from ctypes import wintypes

        # instâncias próprias: declarar tipos em ctypes.windll mudaria as funções para o processo todo
        u = self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        k = self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        H = wintypes.HANDLE
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
        u.SendInput.restype = wintypes.UINT
        u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u.GetAsyncKeyState.restype = ctypes.c_short
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.CloseClipboard.restype = wintypes.BOOL
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.GetClipboardData.restype = H
        k.GlobalLock.argtypes = [H]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [H]
        k.GlobalUnlock.restype = wintypes.BOOL

    def sequence(self) -> int:
        return int(self._user32.GetClipboardSequenceNumber())

    def send_copy(self) -> None:
        def key(vk: int, up: bool) -> _INPUT:
            i = _INPUT(type=_INPUT_KEYBOARD)
            i.ki.wVk = vk
            i.ki.dwFlags = _KEYEVENTF_KEYUP if up else 0
            return i

        events = [key(_VK_CONTROL, True), key(_VK_CONTROL, False), key(_VK_C, False),
                  key(_VK_C, True), key(_VK_CONTROL, True)]
        arr = (_INPUT * len(events))(*events)
        sent = self._user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))
        if sent != len(events):
            raise OSError(f"SendInput enviou {sent} de {len(events)} eventos")

    def wait_modifiers_released(self, timeout_s: float) -> None:
        keys = (_VK_CONTROL, _VK_MENU, _VK_SHIFT, _VK_LWIN, _VK_RWIN)
        deadline = time.monotonic() + timeout_s
        while any(self._user32.GetAsyncKeyState(vk) & 0x8000 for vk in keys):
            if time.monotonic() >= deadline:
                return
            time.sleep(0.01)

    def read_text(self) -> str:
        u, k = self._user32, self._kernel32
        deadline = time.monotonic() + 0.1
        while not u.OpenClipboard(None):
            if time.monotonic() >= deadline:
                return ""
            time.sleep(0.01)
        try:
            handle = u.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = k.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                return ctypes.wstring_at(ptr)
            finally:
                k.GlobalUnlock(handle)
        finally:
            u.CloseClipboard()

    def read_primary(self) -> str | None:
        return None


class QtBackend:
    """Outros sistemas via Qt. Só na thread da interface."""

    def __init__(self) -> None:
        from PySide6.QtGui import QClipboard, QGuiApplication

        self._cb = QGuiApplication.clipboard()
        self._mode = QClipboard.Mode

    def sequence(self) -> int:
        return 0

    def send_copy(self) -> None:
        pass

    def wait_modifiers_released(self, timeout_s: float) -> None:
        pass

    def read_text(self) -> str:
        return self._cb.text()

    def read_primary(self) -> str | None:
        if not self._cb.supportsSelection():
            return None
        return self._cb.text(self._mode.Selection)


def default_backend() -> Backend:
    return WinBackend() if sys.platform == "win32" else QtBackend()
