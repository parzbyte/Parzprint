"""Motores de OCR. A interface só conhece ``OcrEngine`` e ``TextBlock``."""

from __future__ import annotations

from .base import OcrEngine, OcrError, TextBlock, join_text, reading_order

__all__ = ["OcrEngine", "OcrError", "TextBlock", "get_engine", "join_text", "reading_order"]


_engines: dict[str, OcrEngine] = {}


def get_engine(name: str) -> OcrEngine:
    """Devolve o motor pedido, reaproveitando a instância (o modelo carrega uma vez só)."""
    if name not in _engines:
        if name == "indra":
            from .indra import IndraEngine

            _engines[name] = IndraEngine()
        else:
            raise OcrError(f"Motor de OCR desconhecido: {name}")
    return _engines[name]
