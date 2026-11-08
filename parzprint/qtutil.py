"""Conversões entre Pillow e Qt."""

from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def pil_to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    q = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return q.copy()  # desacopla do buffer Python


def pil_to_qpixmap(image: Image.Image, scale: float = 1.0) -> QPixmap:
    pm = QPixmap.fromImage(pil_to_qimage(image))
    pm.setDevicePixelRatio(scale)
    return pm


def qimage_to_pil(qimage: QImage) -> Image.Image:
    """QImage -> imagem RGBA do Pillow."""
    q = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = q.width(), q.height()
    data = bytes(q.constBits())[: q.bytesPerLine() * h]
    return Image.frombuffer("RGBA", (w, h), data, "raw", "RGBA", q.bytesPerLine(), 1).copy()
