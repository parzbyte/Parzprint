"""Atalho global de captura (pynput). Em Wayland não há atalho global para apps comuns."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping

from .settings import MODIFIERS, is_valid_hotkey

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


class GlobalHotkey:
    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self.hotkey = hotkey
        self._callback = callback
        self._listener = None

    def start(self) -> None:
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
        self._listener = listener

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def rebind(self, hotkey: str) -> None:
        to_pynput(hotkey)  # valida antes de derrubar o atual
        self.stop()
        self.hotkey = hotkey
        self.start()
