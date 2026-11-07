"""Motores de OCR. A interface só conhece ``OcrEngine`` e ``TextBlock``."""

from __future__ import annotations

from .base import OcrEngine, OcrError, TextBlock, join_text, reading_order

__all__ = ["OcrEngine", "OcrError", "TextBlock", "get_engine", "join_text", "reading_order"]


def get_engine(name: str) -> OcrEngine:
    if name == "indra":
        from .indra import IndraEngine

        return IndraEngine()
    raise OcrError(f"Motor de OCR desconhecido: {name}")
