"""Roda o OCR fora da thread da interface.

Usa uma ``threading.Thread`` daemon em vez de ``QThread``: se o app for fechado com o
OCR ainda rodando (por exemplo durante o download do modelo), o processo sai normalmente
em vez de abortar com "QThread destroyed while thread is still running".
"""

from __future__ import annotations

import threading

from PIL import Image
from PySide6.QtCore import QObject, Signal

from .ocr.base import OcrEngine

_running: set["OcrWorker"] = set()  # mantém o objeto vivo até o resultado chegar


def progress_label(engine: OcrEngine) -> str:
    if getattr(engine, "name", "") == "indra":
        from .ocr.indra import is_model_cached

        if not is_model_cached():
            return "Baixando modelo… (só na primeira vez)"
    return "Lendo texto…"


class OcrWorker(QObject):
    # emitidos da thread de trabalho; o Qt entrega na thread da interface (fila)
    finished_ok = Signal(list)
    failed = Signal(str)
    _done = Signal()

    def __init__(self, engine: OcrEngine, image: Image.Image):
        super().__init__(None)
        self._engine = engine
        self._image = image.copy()
        self._thread = threading.Thread(target=self._run, name="parzprint-ocr", daemon=True)
        self._done.connect(self._cleanup)

    def start(self) -> None:
        _running.add(self)
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        try:
            blocks = self._engine.recognize(self._image)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e) or type(e).__name__)
        else:
            self.finished_ok.emit(blocks)
        self._done.emit()

    def _cleanup(self) -> None:
        _running.discard(self)
