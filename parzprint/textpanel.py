"""Painel de texto (OCR): modelo de seleção dos blocos e a janela lateral."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from .ocr.base import TextBlock, join_text

EMPTY_MESSAGE = "Nenhum texto encontrado"


class TextSelectionModel:
    """Blocos de texto (já em ordem de leitura) e quais estão selecionados. Sem Qt."""

    def __init__(self, blocks: list[TextBlock]):
        self.blocks = list(blocks)
        self._selected: set[int] = set()

    def hit(self, x: int, y: int) -> int | None:
        for i, b in enumerate(self.blocks):
            if b.x <= x < b.x + b.width and b.y <= y < b.y + b.height:
                return i
        return None

    def select_only(self, i: int) -> None:
        self._selected = {i} if 0 <= i < len(self.blocks) else set()

    def select_range_by_drag(self, rect: tuple[int, int, int, int]) -> None:
        x, y, w, h = rect
        x0, x1 = sorted((x, x + w))
        y0, y1 = sorted((y, y + h))
        self._selected = {
            i
            for i, b in enumerate(self.blocks)
            if b.x < x1 and x0 < b.x + b.width and b.y < y1 and y0 < b.y + b.height
        }

    def clear(self) -> None:
        self._selected = set()

    def selected_indices(self) -> list[int]:
        return sorted(self._selected)

    def selected_text(self) -> str:
        return join_text([self.blocks[i] for i in self.selected_indices()])

    def all_text(self) -> str:
        return join_text(self.blocks)


PANEL_STYLE = """
QWidget#panel { background: rgba(32, 32, 32, 245); border: 1px solid rgba(255,255,255,50); border-radius: 8px; }
QLabel { color: #EEEEEE; }
QLabel#title { font-weight: bold; }
QLabel#status { color: #BBBBBB; }
QPlainTextEdit { background: #1B1B1B; color: #F2F2F2; border: 1px solid #444; border-radius: 4px;
                 selection-background-color: #1E88E5; font-size: 13px; }
QPushButton { background: #2D2D2D; color: #EEEEEE; border: 1px solid #555; border-radius: 4px; padding: 5px 10px; }
QPushButton:hover { background: #3A3A3A; }
QPushButton:disabled { color: #777; border-color: #3A3A3A; }
QPushButton#primary { background: #1E88E5; border-color: #1E88E5; }
QPushButton#primary:hover { background: #2196F3; }
"""


class TextPanel(QWidget):
    hover_block = Signal(object)  # int | None
    copy_all = Signal(str)
    copy_selection = Signal()
    closed = Signal()
    retry = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(PANEL_STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Texto da imagem", self)
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        self.close_button = QPushButton("Fechar painel", self)
        self.close_button.clicked.connect(self.closed)
        head.addWidget(self.close_button)
        lay.addLayout(head)

        self.status = QLabel(self)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.edit = QPlainTextEdit(self)
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.edit.viewport().setMouseTracking(True)
        self.edit.viewport().installEventFilter(self)
        lay.addWidget(self.edit, 1)

        row = QHBoxLayout()
        self.copy_all_button = QPushButton("Copiar tudo", self)
        self.copy_all_button.setObjectName("primary")
        self.copy_all_button.clicked.connect(lambda: self.copy_all.emit(self.edit.toPlainText()))
        self.copy_sel_button = QPushButton("Copiar seleção", self)
        self.copy_sel_button.clicked.connect(self.copy_selection)
        self.copy_sel_button.ensurePolished()
        self.copy_sel_button.setMinimumWidth(
            self.copy_sel_button.fontMetrics().horizontalAdvance("Copiar seleção (999)") + 28
        )
        self.retry_button = QPushButton("Tentar de novo", self)
        self.retry_button.clicked.connect(self.retry)
        row.addWidget(self.copy_all_button)
        row.addWidget(self.copy_sel_button)
        row.addWidget(self.retry_button)
        row.addStretch(1)
        lay.addLayout(row)
        self.show_loading("")

    # ---------- estados ----------
    def show_loading(self, label: str) -> None:
        self.status.setText(label)
        self.status.setVisible(bool(label))
        self.edit.setPlainText("")
        self.edit.setEnabled(False)
        self.copy_all_button.setEnabled(False)
        self.copy_sel_button.setEnabled(False)
        self.retry_button.hide()

    def show_blocks(self, blocks: list[TextBlock]) -> None:
        self.retry_button.hide()
        self.edit.setEnabled(True)
        if not blocks:
            self.status.setText(EMPTY_MESSAGE)
            self.status.show()
            self.edit.setPlainText("")
            self.copy_all_button.setEnabled(False)
        else:
            self.status.setText("Passe o mouse ou arraste sobre a imagem para escolher trechos.")
            self.status.show()
            self.edit.setPlainText(join_text(blocks))
            self.copy_all_button.setEnabled(True)
        self.set_selection_count(0)

    def show_error(self, message: str) -> None:
        self.status.setText(f"Não foi possível ler o texto: {message}")
        self.status.show()
        self.edit.setPlainText("")
        self.edit.setEnabled(False)
        self.copy_all_button.setEnabled(False)
        self.copy_sel_button.setEnabled(False)
        self.retry_button.show()

    def set_selection_count(self, n: int) -> None:
        self.copy_sel_button.setEnabled(n > 0)
        self.copy_sel_button.setText(f"Copiar seleção ({n})" if n else "Copiar seleção")

    # ---------- destaque ----------
    def highlight_block(self, i: int | None) -> None:
        selections = []
        if i is not None:
            block = self.edit.document().findBlockByNumber(i)
            if block.isValid():
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(QColor(30, 136, 229, 90))
                sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                sel.cursor = QTextCursor(block)
                selections.append(sel)
        self.edit.setExtraSelections(selections)

    def eventFilter(self, obj, event):
        if obj is self.edit.viewport():
            if event.type() == QEvent.Type.MouseMove:
                cursor = self.edit.cursorForPosition(event.position().toPoint())
                self.hover_block.emit(cursor.blockNumber())
            elif event.type() == QEvent.Type.Leave:
                self.hover_block.emit(None)
        return super().eventFilter(obj, event)
