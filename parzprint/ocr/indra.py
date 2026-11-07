"""Adaptador do Indra OCR (local, CPU, sem API)."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
from PIL import Image

from .base import OcrError, TextBlock, reading_order


def is_model_cached() -> bool:
    """True se o modelo do Indra já está no cache local (nenhum download será feito)."""
    try:
        from huggingface_hub import snapshot_download
        from indra_ocr.models import HF_REPO, HF_REVISION, MATH_FILES

        # Mesmos filtros que indra_ocr.models.model_dir usa: só os arquivos do modelo.
        snapshot_download(
            HF_REPO,
            revision=HF_REVISION,
            local_files_only=True,
            allow_patterns=["*.onnx", "meta.json", "lm.npz", "lm_*.npz"],
            ignore_patterns=list(MATH_FILES),
        )
        return True
    except Exception:  # noqa: BLE001
        return False


class IndraEngine:
    name = "indra"

    def __init__(self, threads: int = 4):
        self._threads = threads
        self._converter: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._converter is None:
                import indra_ocr

                self._converter = indra_ocr.load(threads=self._threads, mode="ocr")
            return self._converter

    def _run_model(self, gray: np.ndarray) -> Any:
        return self._load().ocr(gray)

    def _to_blocks(self, page: Any, width: int, height: int) -> list[TextBlock]:
        blocks = []
        for line in page.lines:
            text = (line.text or "").strip()
            if not text:
                continue
            x0, y0, x1, y1 = line.box
            x0, x1 = max(0, int(x0)), min(width, int(x1))
            y0, y1 = max(0, int(y0)), min(height, int(y1))
            if x1 <= x0 or y1 <= y0:
                continue
            blocks.append(TextBlock(text, x0, y0, x1 - x0, y1 - y0))
        return reading_order(blocks)

    def recognize(self, image: Image.Image) -> list[TextBlock]:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        try:
            page = self._run_model(gray)
            return self._to_blocks(page, image.width, image.height)
        except OcrError:
            raise
        except Exception as e:  # noqa: BLE001
            raise OcrError(str(e)) from e
