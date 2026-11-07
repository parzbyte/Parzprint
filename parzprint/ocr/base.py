"""Interface comum dos motores de OCR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class TextBlock:
    text: str
    x: int
    y: int
    width: int
    height: int


class OcrError(Exception):
    """Falha ao reconhecer texto (motor ausente, modelo indisponível, erro interno)."""


class OcrEngine(Protocol):
    name: str

    def recognize(self, image: Image.Image) -> list[TextBlock]: ...


def reading_order(blocks: list[TextBlock]) -> list[TextBlock]:
    """Ordena em linhas (de cima para baixo) e, dentro da linha, da esquerda para a direita.

    Dois blocos estão na mesma linha quando seus centros verticais distam menos que
    metade da altura média dos blocos.
    """
    if not blocks:
        return []
    tolerance = sum(b.height for b in blocks) / len(blocks) / 2
    rows: list[list[TextBlock]] = []
    for b in sorted(blocks, key=lambda b: b.y + b.height / 2):
        center = b.y + b.height / 2
        if rows:
            row = rows[-1]
            row_center = sum(r.y + r.height / 2 for r in row) / len(row)
            if abs(center - row_center) < tolerance:
                row.append(b)
                continue
        rows.append([b])
    return [b for row in rows for b in sorted(row, key=lambda b: b.x)]


def join_text(blocks: list[TextBlock]) -> str:
    return "\n".join(b.text for b in blocks)
