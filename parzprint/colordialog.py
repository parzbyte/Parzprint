"""Escolha de cor: no Windows usa a janela "Cor" do próprio sistema (a mesma do Lightshot);
nos outros sistemas, a do Qt."""

from __future__ import annotations

import sys

from .annotations import PALETTE

# cores personalizadas da janela do Windows, lembradas enquanto o app está aberto
_custom: list[int] = []


def to_colorref(color: str) -> int:
    """"#RRGGBB" -> COLORREF do Windows (0x00BBGGRR)."""
    h = color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def from_colorref(value: int) -> str:
    r, g, b = value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def _choose_windows(initial: str, owner_hwnd: int, at: tuple[int, int] | None = None) -> str | None:
    import ctypes
    from ctypes import wintypes

    class CHOOSECOLORW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD),
            ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HWND),
            ("rgbResult", wintypes.DWORD),
            ("lpCustColors", ctypes.POINTER(wintypes.DWORD)),
            ("Flags", wintypes.DWORD),
            ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", wintypes.LPCWSTR),
        ]

    CC_RGBINIT, CC_ENABLEHOOK, CC_ANYCOLOR = 0x1, 0x10, 0x100
    WM_INITDIALOG = 0x0110
    SWP_NOSIZE, SWP_NOZORDER = 0x1, 0x4
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_size_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    def hook(hwnd, msg, wparam, lparam):
        if msg == WM_INITDIALOG and at is not None:
            # abre ao lado do botão de cor, como no Lightshot (sem sair da tela)
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w, h = rect.right - rect.left, rect.bottom - rect.top
            mon = ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(*at), 2)

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(mon, ctypes.byref(info))
            work = info.rcWork
            x = min(max(at[0], work.left), work.right - w)
            y = min(max(at[1], work.top), work.bottom - h)
            ctypes.windll.user32.SetWindowPos(hwnd, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER)
            return 1
        return 0

    hook_proc = HOOKPROC(hook)
    if not _custom:
        _custom.extend([to_colorref(c) for c in PALETTE] + [0x00FFFFFF] * (16 - len(PALETTE)))
    custom = (wintypes.DWORD * 16)(*_custom)
    cc = CHOOSECOLORW()
    cc.lStructSize = ctypes.sizeof(CHOOSECOLORW)
    cc.hwndOwner = owner_hwnd
    cc.rgbResult = to_colorref(initial)
    cc.lpCustColors = custom
    cc.Flags = CC_RGBINIT | CC_ANYCOLOR | CC_ENABLEHOOK
    cc.lpfnHook = ctypes.cast(hook_proc, ctypes.c_void_p)
    ok = ctypes.windll.comdlg32.ChooseColorW(ctypes.byref(cc))
    _custom[:] = list(custom)
    return from_colorref(cc.rgbResult) if ok else None


def choose_color(initial: str, parent) -> str | None:
    """Abre a janela de cores e devolve "#RRGGBB", ou None se o usuário cancelar."""
    if sys.platform == "win32":
        try:
            hwnd = int(parent.window().winId()) if parent is not None else 0
            at = None
            if parent is not None:
                g = parent.mapToGlobal(parent.rect().topRight())
                dpr = parent.devicePixelRatioF()
                at = (round((g.x() + 8) * dpr), round(g.y() * dpr))
            return _choose_windows(initial, hwnd, at)
        except (OSError, AttributeError):
            pass  # cai para a janela do Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    dialog = QColorDialog(QColor(initial), parent.window() if parent is not None else None)
    dialog.setWindowTitle("Cor")
    from PySide6.QtCore import Qt

    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    if dialog.exec() == QColorDialog.DialogCode.Accepted:
        return dialog.selectedColor().name().upper()
    return None
