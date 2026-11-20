"""Borda vermelha em volta da área gravada e a contagem antes de começar (fora do vídeo)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import brand
from .exclude import exclude_from_capture

BORDER = 2
BORDER_COLOR = QColor(brand.RED)


class AreaFrame(QWidget):
    def __init__(self, area: QRect):
        super().__init__(None)
        self.area = QRect(area)
        self.count = 0
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(area.adjusted(-BORDER, -BORDER, BORDER, BORDER))

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)

    def show_count(self, seconds: int) -> None:
        self.count = seconds
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(BORDER_COLOR, BORDER)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        r = self.rect()
        p.drawRect(r.adjusted(BORDER // 2, BORDER // 2, -(BORDER + 1) // 2, -(BORDER + 1) // 2))
        if self.count > 0:
            side = min(160, self.area.width() - 20, self.area.height() - 20)
            if side > 20:
                box = QRect(0, 0, side, side)
                box.moveCenter(r.center())
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 170))
                p.drawEllipse(box)
                f = QFont()
                f.setPixelSize(int(side * 0.55))
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#FFFFFF"))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, str(self.count))
        p.end()
