"""Roda o OCR fora da thread da interface."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QThread, Signal

from .ocr.base import OcrEngine

_running: set["OcrWorker"] = set()  # mantém a thread viva mesmo se o editor fechar


def progress_label(engine: OcrEngine) -> str:
    if getattr(engine, "name", "") == "indra":
        from .ocr.indra import is_model_cached

        if not is_model_cached():
            return "Baixando modelo… (só na primeira vez)"
    return "Lendo texto…"


class OcrWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, engine: OcrEngine, image: Image.Image):
        super().__init__(None)
        self._engine = engine
        self._image = image.copy()
        self.finished.connect(self._cleanup)

    def start(self, *args, **kwargs) -> None:
        _running.add(self)
        super().start(*args, **kwargs)

    def run(self) -> None:
        try:
            blocks = self._engine.recognize(self._image)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e) or type(e).__name__)
            return
        self.finished_ok.emit(blocks)

    def _cleanup(self) -> None:
        _running.discard(self)
        self.deleteLater()
