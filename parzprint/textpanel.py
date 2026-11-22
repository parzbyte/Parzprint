"""Texto da imagem (OCR): o modelo de seleção contínua e o painel lateral.

A seleção funciona como num editor de texto (e como no Google Lens): arrasta-se de um
caractere a outro e o trecho entre os dois fica selecionado, mesmo no meio da linha.
O Indra dá a caixa de cada linha; a posição de cada caractere dentro dela é estimada
pela largura relativa das letras (``measure``).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .ocr.base import TextBlock

EMPTY_MESSAGE = "Nenhum texto encontrado"
HINT = "Arraste sobre o texto da imagem para selecionar. Clique duas vezes numa palavra para pegá-la."


class TextLayout:
    """Linhas reconhecidas, posição de cada caractere e o trecho selecionado. Sem janelas."""

    def __init__(self, blocks: list[TextBlock], measure: Callable[[str], float] | None = None):
        self.blocks = list(blocks)
        self.lines = [b.text for b in self.blocks]
        self.text = "\n".join(self.lines)
        measure = measure or len
        self.starts: list[int] = []
        self.edges: list[list[float]] = []
        offset = 0
        for b, line in zip(self.blocks, self.lines):
            self.starts.append(offset)
            offset += len(line) + 1
            total = measure(line) or 1
            k = b.width / total
            self.edges.append([b.x + measure(line[:i]) * k for i in range(len(line) + 1)])
        self._sel = (0, 0)

    # ---------- posição ----------
    def _line_at(self, x: float, y: float) -> int:
        def distance(i: int) -> tuple[float, float]:
            b = self.blocks[i]
            dy = 0.0 if b.y <= y <= b.y + b.height else min(abs(y - b.y), abs(y - b.y - b.height))
            dx = 0.0 if b.x <= x <= b.x + b.width else min(abs(x - b.x), abs(x - b.x - b.width))
            return dy, dx

        return min(range(len(self.blocks)), key=distance)

    def line_of(self, offset: int) -> int:
        i = 0
        for j, start in enumerate(self.starts):
            if start <= offset:
                i = j
        return i

    def position_at(self, x: float, y: float) -> int:
        """Posição no texto (0..len) mais próxima do ponto (coordenadas da imagem)."""
        if not self.blocks:
            return 0
        i = self._line_at(x, y)
        edges = self.edges[i]
        col = min(range(len(edges)), key=lambda c: abs(edges[c] - x))
        return self.starts[i] + col

    def is_over_text(self, x: float, y: float, pad: float = 4) -> bool:
        return any(
            b.x - pad <= x <= b.x + b.width + pad and b.y - pad <= y <= b.y + b.height + pad for b in self.blocks
        )

    def word_at(self, offset: int) -> tuple[int, int]:
        t = self.text
        if not t:
            return 0, 0
        offset = max(0, min(offset, len(t)))
        if offset == len(t) or not t[offset].isalnum():
            if offset > 0 and t[offset - 1].isalnum():
                offset -= 1
            else:
                return offset, offset
        a = b = offset
        while a > 0 and t[a - 1].isalnum():
            a -= 1
        while b < len(t) and t[b].isalnum():
            b += 1
        return a, b

    # ---------- seleção ----------
    def select(self, anchor: int, focus: int) -> None:
        n = len(self.text)
        a, b = sorted((max(0, min(anchor, n)), max(0, min(focus, n))))
        self._sel = (a, b)

    def select_all(self) -> None:
        self._sel = (0, len(self.text))

    def clear(self) -> None:
        self._sel = (0, 0)

    @property
    def selection(self) -> tuple[int, int]:
        return self._sel

    def has_selection(self) -> bool:
        return self._sel[1] > self._sel[0]

    def selected_text(self) -> str:
        a, b = self._sel
        return self.text[a:b]

    def selection_rects(self) -> list[tuple[int, int, int, int]]:
        """Um retângulo (x0, y0, x1, y1) por linha tocada pela seleção."""
        a, b = self._sel
        if b <= a:
            return []
        rects = []
        for i, blk in enumerate(self.blocks):
            start, end = self.starts[i], self.starts[i] + len(self.lines[i])
            lo, hi = max(a, start), min(b, end)
            if lo >= hi:
                continue
            x0 = self.edges[i][lo - start]
            x1 = self.edges[i][hi - start]
            rects.append((round(x0), blk.y, round(x1), blk.y + blk.height))
        return rects


PANEL_STYLE = """
QWidget#panel { background: rgba(17, 17, 17, 246); border: 1px solid rgba(255,255,255,45); border-radius: 9px; }
QLabel { color: #ECECEC; }
QLabel#title { font-weight: bold; font-size: 13px; }
QLabel#status { color: #A8A8A8; }
QPlainTextEdit { background: #1C1C1C; color: #F2F2F2; border: 1px solid #3A3A3A; border-radius: 6px;
                 selection-background-color: #E11D2E; selection-color: #FFFFFF; font-size: 13px; padding: 4px; }
QPushButton { background: #2A2A2A; color: #ECECEC; border: 1px solid #444444; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background: #3A3A3A; }
QPushButton:disabled { color: #6A6A6A; border-color: #3A3A3A; }
QPushButton#primary { background: #E11D2E; border-color: #E11D2E; color: #FFFFFF; }
QPushButton#primary:hover { background: #A3111F; border-color: #A3111F; }
"""


class TextPanel(QWidget):
    copy_all = Signal(str)
    copy_selection = Signal(str)
    translate = Signal(str)
    closed = Signal()
    retry = Signal()
    selection_changed = Signal(int, int)  # o usuário selecionou no painel (posições no texto)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(PANEL_STYLE)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._syncing = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
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
        self.edit.selectionChanged.connect(self._on_edit_selection)
        lay.addWidget(self.edit, 1)

        row = QHBoxLayout()
        self.copy_all_button = QPushButton("Copiar tudo", self)
        self.copy_all_button.setObjectName("primary")
        self.copy_all_button.clicked.connect(lambda: self.copy_all.emit(self.edit.toPlainText()))
        self.copy_sel_button = QPushButton("Copiar seleção", self)
        self.copy_sel_button.clicked.connect(lambda: self.copy_selection.emit(self.selected_text()))
        self.translate_button = QPushButton("Traduzir", self)
        self.translate_button.clicked.connect(self._on_translate)
        self.retry_button = QPushButton("Tentar de novo", self)
        self.retry_button.clicked.connect(self.retry)
        row.addWidget(self.copy_all_button)
        row.addWidget(self.copy_sel_button)
        row.addWidget(self.translate_button)
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
        self.translate_button.setEnabled(False)
        self.retry_button.hide()

    def show_text(self, text: str) -> None:
        self.retry_button.hide()
        self.edit.setEnabled(True)
        self._syncing = True
        self.edit.setPlainText(text)
        self._syncing = False
        self.status.setText(HINT if text else EMPTY_MESSAGE)
        self.status.show()
        self.copy_all_button.setEnabled(bool(text))
        self.copy_sel_button.setEnabled(False)
        self.translate_button.setEnabled(bool(text))

    def show_error(self, message: str) -> None:
        self.status.setText(f"Não foi possível ler o texto: {message}")
        self.status.show()
        self.edit.setPlainText("")
        self.edit.setEnabled(False)
        self.copy_all_button.setEnabled(False)
        self.copy_sel_button.setEnabled(False)
        self.translate_button.setEnabled(False)
        self.retry_button.show()

    # ---------- seleção sincronizada ----------
    def is_edited(self) -> bool:
        return self.edit.document().isModified()

    def set_selection(self, a: int, b: int) -> None:
        """Espelha a seleção feita na imagem (só se o texto não foi editado)."""
        if self.is_edited():
            return
        self._syncing = True
        cursor = self.edit.textCursor()
        cursor.setPosition(a)
        cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        self.edit.setTextCursor(cursor)
        self._syncing = False
        self.copy_sel_button.setEnabled(b > a)

    def selected_text(self) -> str:
        return self.edit.textCursor().selectedText().replace(" ", "\n")

    def _on_translate(self) -> None:
        """Traduz o trecho selecionado ou, sem seleção, o texto todo."""
        text = self.selected_text() if self.edit.textCursor().hasSelection() else self.edit.toPlainText()
        self.translate.emit(text)

    def _on_edit_selection(self) -> None:
        cursor = self.edit.textCursor()
        self.copy_sel_button.setEnabled(cursor.hasSelection())
        if self._syncing or self.is_edited():
            return
        self.selection_changed.emit(cursor.selectionStart(), cursor.selectionEnd())
