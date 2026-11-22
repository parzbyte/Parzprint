"""Atalho global de captura.

No Windows o atalho é registrado no próprio sistema (RegisterHotKey, como faz o Lightshot):
a combinação vai só para o Parzprint e não chega ao programa em foco. No Linux (X11) usa o
pynput, que só escuta. Em Wayland não há atalho global para apps comuns.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable, Mapping

from .settings import MODIFIERS, is_valid_hotkey

log = logging.getLogger(__name__)

_MOD_TO_PYNPUT = {"Ctrl": "<ctrl>", "Shift": "<shift>", "Alt": "<alt>", "Win": "<cmd>"}
_SPECIAL = {
    "Print": "print_screen",
    "Space": "space",
    "Esc": "esc",
    "Tab": "tab",
    "Home": "home",
    "End": "end",
    "Insert": "insert",
    "Delete": "delete",
    "Del": "delete",
    "Ins": "insert",
    "PgUp": "page_up",
    "PgDown": "page_down",
    "Pause": "pause",
}


# modificadores do RegisterHotKey
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_WIN_MODS = {"Ctrl": MOD_CONTROL, "Shift": MOD_SHIFT, "Alt": MOD_ALT, "Win": MOD_WIN}
_WIN_VK = {
    "Print": 0x2C, "Space": 0x20, "Esc": 0x1B, "Tab": 0x09, "Home": 0x24, "End": 0x23,
    "Insert": 0x2D, "Ins": 0x2D, "Delete": 0x2E, "Del": 0x2E, "PgUp": 0x21, "PgDown": 0x22,
    "Pause": 0x13,
}
ERROR_HOTKEY_ALREADY_REGISTERED = 1409


class HotkeyError(Exception):
    """Atalho inválido ou impossível de registrar."""


def to_pynput(hotkey: str) -> str:
    if not is_valid_hotkey(hotkey):
        raise HotkeyError(f"Atalho inválido: {hotkey!r}")
    *mods, key = hotkey.split("+")
    if key in _SPECIAL:
        k = f"<{_SPECIAL[key]}>"
    elif len(key) > 1 and key[0] in "Ff" and key[1:].isdigit():
        k = f"<f{key[1:]}>"
    elif len(key) == 1:
        k = key.lower()
    else:
        raise HotkeyError(f"Tecla não suportada: {key!r}")
    return "+".join([_MOD_TO_PYNPUT[m] for m in mods] + [k])


def to_win32(hotkey: str) -> tuple[int, int]:
    """"Ctrl+Alt+S" -> (modificadores, código virtual da tecla) para o RegisterHotKey."""
    if not is_valid_hotkey(hotkey):
        raise HotkeyError(f"Atalho inválido: {hotkey!r}")
    *mods, key = hotkey.split("+")
    flags = MOD_NOREPEAT
    for m in mods:
        flags |= _WIN_MODS[m]
    if key in _WIN_VK:
        vk = _WIN_VK[key]
    elif len(key) > 1 and key[0] in "Ff" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and key.upper().isascii() and key.upper().isalnum():
        vk = ord(key.upper())
    elif len(key) == 1 and sys.platform == "win32":
        import ctypes

        code = ctypes.windll.user32.VkKeyScanW(ord(key))
        if code == -1:
            raise HotkeyError(f"Tecla não suportada: {key!r}")
        vk = code & 0xFF
    else:
        raise HotkeyError(f"Tecla não suportada: {key!r}")
    return flags, vk


_MOD_VK = {"Ctrl": 0x11, "Shift": 0x10, "Alt": 0x12, "Win": 0x5B}


def _async_key_state(vk: int) -> bool:
    import ctypes

    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def is_key_down(hotkey: str, state_fn: Callable[[int], bool] | None = None) -> bool:
    """True se todas as teclas da combinação estão apertadas agora (Windows)."""
    state_fn = state_fn or _async_key_state
    try:
        _flags, vk = to_win32(hotkey)
    except HotkeyError:
        return False
    *mods, _key = hotkey.split("+")
    return all(state_fn(_MOD_VK[m]) for m in mods) and state_fn(vk)


class _WindowsHotkey(threading.Thread):
    """Registra o atalho no Windows numa thread com o próprio laço de mensagens."""

    WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        super().__init__(name="parzprint-hotkey", daemon=True)
        self._mods, self._vk = to_win32(hotkey)
        self._hotkey = hotkey
        self._callback = callback
        self._ready = threading.Event()
        self._error: str | None = None
        self._tid = 0

    def run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32")
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, self._mods, self._vk):
            err = ctypes.get_last_error()
            if err == ERROR_HOTKEY_ALREADY_REGISTERED:
                self._error = f"o atalho {self._hotkey} já está em uso por outro programa"
            else:
                self._error = f"o Windows recusou o atalho {self._hotkey} (erro {err})"
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY:
                    self._fire()
        finally:
            user32.UnregisterHotKey(None, 1)

    def _fire(self) -> None:
        # uma falha no callback não pode encerrar o laço e desligar o atalho
        try:
            self._callback()
        except Exception:  # noqa: BLE001
            log.exception("Falha no atalho %s", self._hotkey)

    def start_and_wait(self) -> None:
        self.start()
        if not self._ready.wait(3):
            raise HotkeyError(f"Não foi possível registrar o atalho {self._hotkey}: sem resposta do Windows")
        if self._error:
            raise HotkeyError(f"Não foi possível registrar: {self._error}")

    def stop(self) -> None:
        import ctypes

        if self.is_alive() and self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, self.WM_QUIT, 0, 0)
            self.join(2)


def from_qt_key_event(modifiers: set[str], key: str) -> str | None:
    """Monta "Ctrl+Shift+S" a partir dos nomes de modificadores e da tecla pressionada."""
    if not modifiers or not key or key in MODIFIERS:
        return None
    mods = [m for m in MODIFIERS if m in modifiers]
    key = key.upper() if len(key) == 1 else key
    text = "+".join(mods + [key])
    return text if is_valid_hotkey(text) else None


def is_wayland(env: Mapping[str, str] = os.environ) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    return env.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(env.get("WAYLAND_DISPLAY"))


READY_TIMEOUT = 3.0


def _wait_ready(listener, timeout: float) -> bool:
    """True se o listener ficou pronto em até ``timeout`` segundos e continua vivo."""
    waiter = threading.Thread(target=listener.wait, daemon=True)
    waiter.start()
    waiter.join(timeout)
    return not waiter.is_alive() and listener.is_alive()


class GlobalHotkey:
    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self.hotkey = hotkey
        self._callback = callback
        self._listener = None

    def start(self) -> None:
        if sys.platform == "win32":
            win = _WindowsHotkey(self.hotkey, self._callback)
            win.start_and_wait()
            self._listener = win
            return
        from pynput import keyboard

        combo = to_pynput(self.hotkey)
        # Listener + HotKey em vez de GlobalHotKeys: no Windows o GlobalHotKeys do
        # pynput 1.8 descarta teclas injetadas (de outros apps, macros e testes).
        try:
            hotkey = keyboard.HotKey(keyboard.HotKey.parse(combo), self._callback)
            listener: keyboard.Listener

            def on_press(key, injected=False):
                hotkey.press(listener.canonical(key))

            def on_release(key, injected=False):
                hotkey.release(listener.canonical(key))

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
        except Exception as e:  # noqa: BLE001
            raise HotkeyError(f"Não foi possível registrar o atalho {self.hotkey}: {e}") from e
        # parar um listener que ainda não abriu trava a conexão com o X; e se o X recusar a
        # conexão, a thread morre e nunca fica pronta: espera com limite em vez de travar o app
        if not _wait_ready(listener, READY_TIMEOUT):
            listener.stop()
            raise HotkeyError(f"Não foi possível ligar o atalho {self.hotkey}: sem resposta do sistema")
        self._listener = listener

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def rebind(self, hotkey: str) -> None:
        to_win32(hotkey) if sys.platform == "win32" else to_pynput(hotkey)  # valida antes de trocar
        self.stop()
        self.hotkey = hotkey
        self.start()
