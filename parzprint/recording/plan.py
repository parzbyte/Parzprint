"""Contas da gravação: tamanho final do vídeo, recorte da área e nomes de arquivo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect

from ..capture import Monitor

_HEIGHTS = {"1080": 1080, "720": 720, "480": 480}


def _even(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def output_size(width: int, height: int, resolution: str) -> tuple[int, int]:
    """Tamanho do vídeo: limita a altura pela resolução escolhida, nunca aumenta, sempre par."""
    target = _HEIGHTS.get(resolution)
    k = min(1.0, target / height) if target and height else 1.0
    return _even(width * k), _even(height * k)


def crop_box(monitor: Monitor, area: QRect) -> tuple[int, int, int, int]:
    """(x, y, largura, altura) da área em pixels físicos da imagem do monitor, dentro dos limites."""
    s = monitor.scale
    lx0 = max(0, area.x() - monitor.x)
    ly0 = max(0, area.y() - monitor.y)
    lx1 = min(monitor.width, area.x() + area.width() - monitor.x)
    ly1 = min(monitor.height, area.y() + area.height() - monitor.y)
    x0, y0 = round(lx0 * s), round(ly0 * s)
    return x0, y0, max(0, round(lx1 * s) - x0), max(0, round(ly1 * s) - y0)


def video_filename(now: datetime) -> str:
    return f"Parzprint_{now:%Y-%m-%d_%H-%M-%S}.mp4"


def temp_path(final: Path) -> Path:
    return final.with_name(final.stem + ".gravando.mp4")
