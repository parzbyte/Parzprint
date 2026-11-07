"""Captura de todos os monitores.

Usa o próprio Qt (``QScreen.grabWindow``): a geometria de cada monitor vem em pixels
lógicos, a mesma unidade das janelas do overlay, e a foto vem em pixels físicos.
``crop`` converte entre os dois, o que mantém o recorte certo com escalas diferentes.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


class CaptureError(Exception):
    """Falha ao fotografar a tela (por exemplo Wayland sem permissão)."""


@dataclass
class Monitor:
    index: int
    x: int
    y: int
    width: int
    height: int
    image: Image.Image
    dpr: float | None = None  # devicePixelRatio do Qt, quando conhecido

    @property
    def scale(self) -> float:
        if self.dpr:
            return self.dpr
        return self.image.width / self.width if self.width else 1.0


def qimage_to_pil(qimage) -> Image.Image:
    from PySide6.QtGui import QImage

    q = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = q.width(), q.height()
    data = bytes(q.constBits())[: q.bytesPerLine() * h]
    return Image.frombuffer("RGBA", (w, h), data, "raw", "RGBA", q.bytesPerLine(), 1).convert("RGB")


def _grab_screens() -> list[Monitor]:
    from PySide6.QtGui import QGuiApplication

    monitors = []
    for i, screen in enumerate(QGuiApplication.screens(), start=1):
        g = screen.geometry()
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            raise CaptureError(f"Não foi possível capturar o monitor {i}")
        image = qimage_to_pil(pixmap.toImage())
        monitors.append(Monitor(i, g.x(), g.y(), g.width(), g.height(), image, screen.devicePixelRatio()))
    return monitors


def grab_all() -> list[Monitor]:
    try:
        monitors = _grab_screens()
    except CaptureError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CaptureError(str(e)) from e
    if not monitors:
        raise CaptureError("Nenhum monitor encontrado")
    return monitors


def monitor_for_point(monitors: list[Monitor], x: int, y: int) -> Monitor | None:
    for m in monitors:
        if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
            return m
    return None


def crop(monitor: Monitor, x: int, y: int, w: int, h: int) -> Image.Image:
    """Recorta a região (coordenadas lógicas globais) da foto do monitor."""
    lx0 = max(0, x - monitor.x)
    ly0 = max(0, y - monitor.y)
    lx1 = min(monitor.width, x - monitor.x + w)
    ly1 = min(monitor.height, y - monitor.y + h)
    s = monitor.scale
    box = (round(lx0 * s), round(ly0 * s), round(lx1 * s), round(ly1 * s))
    return monitor.image.crop(box)
