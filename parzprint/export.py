"""Saídas da captura: salvar em arquivo, copiar para a área de transferência, imprimir."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image

from .settings import Settings

_EXT = {"PNG": ".png", "JPG": ".jpg"}


def default_filename(now: datetime, image_format: str) -> str:
    return f"Parzprint_{now:%Y-%m-%d_%H-%M-%S}{_EXT.get(image_format, '.png')}"


def save_image(image: Image.Image, path: Path, image_format: str) -> Path:
    """Salva no formato da extensão do arquivo; sem extensão conhecida, usa ``image_format``.

    Sem extensão nenhuma, acrescenta a do formato. Devolve o caminho realmente gravado.
    """
    if not path.suffix:
        path = path.with_suffix(_EXT.get(image_format, ".png"))
    ext = path.suffix.lower()
    fmt = "JPG" if ext in (".jpg", ".jpeg") else "PNG" if ext == ".png" else image_format
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "JPG":
        image.convert("RGB").save(path, "JPEG", quality=92)
    else:
        image.save(path, "PNG")
    return path


def copy_image(image: Image.Image) -> None:
    from PySide6.QtWidgets import QApplication

    from .qtutil import pil_to_qimage

    QApplication.clipboard().setImage(pil_to_qimage(image))


def copy_text(text: str) -> None:
    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().setText(text)


def print_image(image: Image.Image, parent) -> bool:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QPainter
    from PySide6.QtPrintSupport import QPrintDialog, QPrinter

    from .qtutil import pil_to_qimage

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimir captura")
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return False
    q = pil_to_qimage(image)
    painter = QPainter(printer)
    page = printer.pageLayout().paintRectPixels(printer.resolution())
    size = q.size().scaled(page.size(), Qt.AspectRatioMode.KeepAspectRatio)
    if q.width() <= page.width() and q.height() <= page.height():
        size = q.size()  # não amplia imagens pequenas
    painter.drawImage(QRect(0, 0, size.width(), size.height()), q)
    painter.end()
    return True


def ask_save_path(parent, settings: Settings, now: datetime) -> Path | None:
    from PySide6.QtWidgets import QFileDialog

    start = Path(settings.save_dir) / default_filename(now, settings.image_format)
    filters = "PNG (*.png);;JPG (*.jpg *.jpeg)" if settings.image_format == "PNG" else "JPG (*.jpg *.jpeg);;PNG (*.png)"
    path, _ = QFileDialog.getSaveFileName(parent, "Salvar captura", str(start), filters)
    return Path(path) if path else None
