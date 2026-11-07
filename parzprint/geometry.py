"""Cálculos de posição: retângulo de seleção, barras e painel. Sem janelas."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

GAP = 6


def normalize_rect(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
    return min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)


def _r(rect: QRect) -> tuple[int, int, int, int]:
    """(esquerda, topo, direita exclusiva, base exclusiva)."""
    return rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height()


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def place_toolbars(sel: QRect, screen: QRect, side_size: QSize, bottom_size: QSize) -> tuple[QPoint, QPoint]:
    """Barra lateral à direita da seleção e inferior abaixo (alinhada à direita).

    Se não couber, vai para a esquerda / acima; se ainda não couber, fica dentro da seleção.
    """
    sl, st, sr, sb = _r(sel)
    l, t, r, b = _r(screen)
    sw, sh = side_size.width(), side_size.height()
    bw, bh = bottom_size.width(), bottom_size.height()

    x = sr + GAP
    if x + sw > r:
        x = sl - GAP - sw
        if x < l:
            x = sr - GAP - sw
    side = QPoint(_clamp(x, l, r - sw), _clamp(st, t, b - sh))

    y = sb + GAP
    if y + bh > b:
        y = st - GAP - bh
        if y < t:
            y = sb - GAP - bh
    bottom = QPoint(_clamp(sr - bw, l, r - bw), _clamp(y, t, b - bh))
    return side, bottom


def place_panel(sel: QRect, screen: QRect, size: QSize, avoid: QRect) -> QPoint:
    """Painel de texto ao lado da seleção (e da barra ``avoid``): direita, senão esquerda."""
    sl, st, sr, _ = _r(sel)
    al, _, ar, _ = _r(avoid)
    l, t, r, b = _r(screen)
    w, h = size.width(), size.height()
    x = max(sr, ar) + GAP
    if x + w > r:
        x = min(sl, al) - GAP - w
        if x < l:
            x = r - GAP - w
    return QPoint(_clamp(x, l, r - w), _clamp(st, t, b - h))
