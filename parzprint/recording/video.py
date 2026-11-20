"""Quadros da gravação: captura da tela, recorte da área, ponteiro do mouse e ritmo."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QImage, QPainter
from PySide6.QtMultimedia import QVideoFrame

_FORMAT = QImage.Format.Format_RGBX8888


def prepare_frame(
    image: QImage, crop: tuple[int, int, int, int], out_size: tuple[int, int],
    cursor: tuple[QImage, int, int] | None = None,
) -> QImage:
    """Recorta ``crop`` (pixels físicos), desenha o ponteiro e reduz para ``out_size``."""
    x, y, w, h = crop
    img = image.copy(QRect(x, y, w, h)).convertToFormat(_FORMAT)
    if cursor is not None:
        pic, cx, cy = cursor
        p = QPainter(img)
        p.drawImage(cx, cy, pic)
        p.end()
    if (img.width(), img.height()) != out_size:
        img = img.scaled(QSize(*out_size), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return img


# ---------------------------------------------------------------- ponteiro (Windows)
_cursor_cache: dict[int, tuple[QImage, int, int]] = {}
_declared = False


def _win32():
    """Declara os tipos das funções do Windows usadas (handles são 64 bits)."""
    global _declared
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    if not _declared:
        H = wintypes.HANDLE
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                           ctypes.POINTER(ctypes.c_void_p), H, wintypes.DWORD]
        gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        gdi32.SelectObject.argtypes = [wintypes.HDC, H]
        gdi32.SelectObject.restype = H
        gdi32.DeleteObject.argtypes = [H]
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        user32.GetIconInfo.argtypes = [H, ctypes.c_void_p]
        user32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, H, ctypes.c_int,
                                      ctypes.c_int, wintypes.UINT, H, wintypes.UINT]
        user32.GetCursorInfo.argtypes = [ctypes.c_void_p]
        _declared = True
    return user32, gdi32


def _cursor_image() -> tuple[QImage, int, int] | None:
    """(imagem do ponteiro atual, hotspot x, hotspot y), ou None se escondido / não Windows."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hCursor", wintypes.HANDLE), ("pt", wintypes.POINT)]

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    user32, gdi32 = _win32()
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(ci)) or not (ci.flags & 1) or not ci.hCursor:
        return None
    key = int(ci.hCursor)
    if key in _cursor_cache:
        return _cursor_cache[key]
    info = ICONINFO()
    if not user32.GetIconInfo(ci.hCursor, ctypes.byref(info)):
        return None
    for bm in (info.hbmMask, info.hbmColor):
        if bm:
            gdi32.DeleteObject(bm)
    size = 64

    def render(bg: int) -> bytes:
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

        hdc = gdi32.CreateCompatibleDC(None)
        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth, bih.biHeight, bih.biPlanes, bih.biBitCount = size, -size, 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
        old = gdi32.SelectObject(hdc, hbmp)
        ctypes.memset(bits, bg, size * size * 4)
        user32.DrawIconEx(hdc, 0, 0, ci.hCursor, 0, 0, 0, None, 3)  # DI_NORMAL
        data = ctypes.string_at(bits, size * size * 4)
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc)
        return data

    import numpy as np

    black = np.frombuffer(render(0), np.uint8).reshape(size, size, 4).astype(np.int16)
    white = np.frombuffer(render(255), np.uint8).reshape(size, size, 4).astype(np.int16)
    alpha = np.clip(255 - (white[..., :3] - black[..., :3]).max(axis=2), 0, 255)
    rgba = np.zeros((size, size, 4), np.uint8)
    nz = alpha > 0
    rgba[..., 0] = black[..., 2]
    rgba[..., 1] = black[..., 1]
    rgba[..., 2] = black[..., 0]
    for c in range(3):
        ch = rgba[..., c].astype(np.int32)
        ch[nz] = np.clip(ch[nz] * 255 // alpha[nz], 0, 255)
        rgba[..., c] = ch
    rgba[..., 3] = alpha
    pic = QImage(rgba.tobytes(), size, size, size * 4, QImage.Format.Format_RGBA8888).copy()
    result = (pic, int(info.xHotspot), int(info.yHotspot))
    _cursor_cache[key] = result
    return result


# ---------------------------------------------------------------- bomba de quadros
class FramePump(QObject):
    """Recebe quadros do monitor, entrega no máximo ``fps`` por segundo, já recortados."""

    frame_ready = Signal(QVideoFrame)
    warning = Signal(str)

    def __init__(self, screen, crop: tuple[int, int, int, int], out_size: tuple[int, int], fps: int,
                 draw_cursor: bool = True, parent=None):
        super().__init__(parent)
        self.screen = screen
        self.crop = crop
        self.out_size = out_size
        self.fps = fps
        self.draw_cursor = draw_cursor
        self._interval = 1_000_000 // fps
        self._last: int | None = None
        self.clock = None
        self._capture = self._session = self._sink = None

    def start(self, clock, capture: bool = True) -> None:
        self.clock = clock
        if not capture:
            return
        from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink

        self._capture = QScreenCapture(self)
        self._capture.setScreen(self.screen)
        self._session = QMediaCaptureSession(self)
        self._session.setScreenCapture(self._capture)
        self._sink = QVideoSink(self)
        self._session.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._capture.errorOccurred.connect(lambda *a: self._on_capture_error(*a))
        self._capture.setActive(True)

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.setActive(False)
            self._sink.videoFrameChanged.disconnect(self._on_frame)
        self._capture = self._session = self._sink = None

    def _on_capture_error(self, _error=None, message: str = "") -> None:
        self.warning.emit(f"A captura da tela falhou: {message or 'erro desconhecido'}")

    def _due(self) -> int | None:
        if self.clock is None or self.clock.paused:
            return None
        now = self.clock.now_us()
        if self._last is not None and now - self._last < self._interval - 2000:
            return None
        return now

    def _on_frame(self, frame) -> None:
        if self._due() is None or not frame.isValid():
            return
        self.handle_image(frame.toImage())

    def _cursor(self):
        if not self.draw_cursor or self.screen is None:
            return None
        try:
            found = _cursor_image()
        except Exception:  # noqa: BLE001  (o ponteiro nunca pode custar o quadro)
            self.draw_cursor = False
            return None
        if found is None:
            return None
        pic, hx, hy = found
        dpr = self.screen.devicePixelRatio()
        pos = QCursor.pos() - self.screen.geometry().topLeft()
        x = round(pos.x() * dpr) - hx - self.crop[0]
        y = round(pos.y() * dpr) - hy - self.crop[1]
        if x > self.crop[2] or y > self.crop[3] or x < -pic.width() or y < -pic.height():
            return None
        return pic, x, y

    def handle_image(self, image: QImage) -> None:
        now = self._due()
        if now is None:
            return
        img = prepare_frame(image, self.crop, self.out_size, self._cursor())
        frame = QVideoFrame(img)
        frame.setStartTime(now)
        frame.setEndTime(now + self._interval)
        self._last = now
        self.frame_ready.emit(frame)
