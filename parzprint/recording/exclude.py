"""Tira uma janela da captura de tela do Windows (ela aparece para a pessoa, mas não no vídeo)."""

from __future__ import annotations

import sys

WDA_EXCLUDEFROMCAPTURE = 0x11


def exclude_from_capture(widget) -> bool:
    """True se o Windows aceitou. Exige Windows 10 2004 ou mais novo."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    fn = ctypes.windll.user32.SetWindowDisplayAffinity
    fn.argtypes = [wintypes.HWND, wintypes.DWORD]
    fn.restype = wintypes.BOOL
    try:
        return bool(fn(int(widget.winId()), WDA_EXCLUDEFROMCAPTURE))
    except (OSError, AttributeError):
        return False
