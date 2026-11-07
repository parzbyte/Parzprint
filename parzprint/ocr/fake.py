"""Motor de OCR falso, para testes e desenvolvimento da interface."""

from __future__ import annotations

from PIL import Image

from .base import TextBlock


class FakeEngine:
    name = "fake"

    def __init__(self, blocks: list[TextBlock]):
        self._blocks = list(blocks)

    def recognize(self, image: Image.Image) -> list[TextBlock]:
        return list(self._blocks)
