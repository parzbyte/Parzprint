"""Janela do tradutor: origem e destino lado a lado, no jeito do Google Tradutor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QCompleter, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizeGrip,
    QVBoxLayout, QWidget,
)

from ..recording.exclude import exclude_from_capture
from ..settings import TRANSLATE_MIN_SIZE, Settings
from .google import clip, web_url
from .languages import AUTO, LANGUAGES, name_of, ordered, push_recent
from .style import STYLE

GAP = 6
DEBOUNCE_MS = 600
WIDE = 560
CODES = frozenset(code for code, _ in LANGUAGES)

LOADING = "Traduzindo..."
CLIPBOARD_HINT = "Texto que estava copiado. Aperte Enter para traduzir."
CLIPPED = "Traduzi só os primeiros 5.000 caracteres."
ERRORS = {
    "network": "Não consegui falar com o Google Tradutor. Confira a internet.",
    "refused": "O Google Tradutor recusou o pedido agora. Espere um pouco e tente de novo.",
    "format": "O Google Tradutor mudou o jeito de responder. Atualize o Parzprint.",
}



def place_window(anchor: QRect, size: QSize, available: QRect) -> QPoint:
    """Abaixo e à direita do ponto; acima se não couber; sempre dentro de ``available``."""
    left, top = available.x(), available.y()
    right, bottom = left + available.width(), top + available.height()
    w, h = size.width(), size.height()
    x = anchor.x()
    y = anchor.y() + anchor.height() + GAP
    if y + h > bottom:
        y = anchor.y() - GAP - h
    return QPoint(max(left, min(x, right - w)), max(top, min(y, bottom - h)))


def _is_enter(event: QKeyEvent) -> bool:
    return event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)


class TranslatorWindow(QWidget):
    def __init__(self, translator, settings: Settings, on_settings_changed: Callable[[Settings], None]):
        super().__init__(None)
        self.translator = translator
        self.settings = settings
        self._on_settings_changed = on_settings_changed
        self._source = settings.translate_source
        self._target = settings.translate_target
        self._detected: str | None = None
        self._translation = ""
        self._pending: int | None = None
        self._last_request: tuple[str, str, str] | None = None
        self._live = False
        self._syncing = False
        self._excluded = False

        self.setWindowTitle("Tradutor")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(STYLE)
        self.setMinimumSize(*TRANSLATE_MIN_SIZE)
        self._build()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.translate_now)
        translator.finished.connect(self._on_finished)
        translator.failed.connect(self._on_failed)

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Tradutor", self)
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        self.pin_button = self._flat("📌", "Manter aberta")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(self.settings.translate_pinned)
        self.pin_button.toggled.connect(self._on_pin)
        close_button = self._flat("×", "Fechar (Esc)")
        close_button.clicked.connect(self.close)
        head.addWidget(self.pin_button)
        head.addWidget(close_button)
        lay.addLayout(head)

        self.source_box = self._language_box()
        self.target_box = self._language_box()
        self.swap_button = QPushButton("⇄", self)
        self.swap_button.setToolTip("Inverter os idiomas")
        self.swap_button.clicked.connect(self.swap)

        self.source_edit = QPlainTextEdit(self)
        self.source_edit.setPlaceholderText("Digite ou cole o texto")
        self.source_edit.installEventFilter(self)
        self.source_edit.textChanged.connect(self._on_text_changed)
        self.result_view = QPlainTextEdit(self)
        self.result_view.setReadOnly(True)

        left = QVBoxLayout()
        left.addWidget(self.source_box)
        left.addWidget(self.source_edit, 1)
        middle = QVBoxLayout()
        middle.addWidget(self.swap_button)
        middle.addStretch(1)
        right = QVBoxLayout()
        right.addWidget(self.target_box)
        right.addWidget(self.result_view, 1)
        self.panes = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.panes.addLayout(left, 1)
        self.panes.addLayout(middle)
        self.panes.addLayout(right, 1)
        lay.addLayout(self.panes, 1)

        self.status = QLabel(self)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        row = QHBoxLayout()
        self.retry_button = QPushButton("Tentar de novo", self)
        self.retry_button.clicked.connect(self.translate_now)
        self.web_button = QPushButton("Abrir no Google Tradutor", self)
        self.web_button.clicked.connect(self._open_web)
        self.translate_button = QPushButton("Traduzir", self)
        self.translate_button.setToolTip("Enter")
        self.translate_button.clicked.connect(self.translate_now)
        self.copy_button = QPushButton("Copiar", self)
        self.copy_button.setObjectName("primary")
        self.copy_button.setToolTip("Ctrl+Enter copia e fecha")
        self.copy_button.clicked.connect(self.copy)
        row.addWidget(self.retry_button)
        row.addWidget(self.web_button)
        row.addStretch(1)
        row.addWidget(self.translate_button)
        row.addWidget(self.copy_button)
        row.addWidget(QSizeGrip(self), 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        lay.addLayout(row)

        self.source_box.currentIndexChanged.connect(lambda _i: self._on_language(self.source_box))
        self.target_box.currentIndexChanged.connect(lambda _i: self._on_language(self.target_box))
        self._fill_boxes()
        self._show_error(None)

    def _flat(self, text: str, tip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("flat")
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def _language_box(self) -> QComboBox:
        box = QComboBox(self)
        box.setEditable(True)
        box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        box.setMaxVisibleItems(16)
        completer = box.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        box.lineEdit().editingFinished.connect(lambda: self._restore_label(box))
        return box

    def _restore_label(self, box: QComboBox) -> None:
        """O que foi digitado para filtrar some e volta o nome do idioma escolhido."""
        box.setEditText(box.itemText(box.currentIndex()))

    def _fill_boxes(self) -> None:
        self._syncing = True
        recent = self.settings.translate_recent
        for box, with_auto, code in (
            (self.source_box, True, self._source),
            (self.target_box, False, self._target),
        ):
            box.clear()
            for item_code, name in ordered(recent, with_auto):
                box.addItem(name, item_code)
            box.setCurrentIndex(max(0, box.findData(code)))
        self._syncing = False
        self._update_detected_label()


    def open(self, text: str, anchor: QRect, auto: bool) -> None:
        """Mostra a janela com ``text``; se já estiver aberta, só troca o texto."""
        if not self.isVisible():
            self._source = self.settings.translate_source
            self._target = self.settings.translate_target
            self._fill_boxes()
            self.pin_button.setChecked(self.settings.translate_pinned)
            width, height = self.settings.translate_size
            self.resize(width, height)
            screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
            self.move(place_window(anchor, self.size(), screen.availableGeometry()))
        self._live = auto
        self._pending = None
        self._translation = ""
        self._forget_detected()
        self._set_source_text(text)
        self.result_view.clear()
        self.status.clear()
        self._show_error(None)
        self._update_swap()
        self.show()
        self.raise_()
        self.activateWindow()
        self.source_edit.setFocus()
        if auto and text:
            self.translate_now()
        elif text:
            self.status.setText(CLIPBOARD_HINT)
            self.source_edit.selectAll()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._excluded:
            self._excluded = True
            exclude_from_capture(self)

    def closeEvent(self, event) -> None:
        self._debounce.stop()
        self._save(translate_size=[self.width(), self.height()], translate_pinned=self.pin_button.isChecked())
        super().closeEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate and self.isVisible() and not self.pin_button.isChecked():
            self.close()
        return super().event(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        wide = self.width() >= WIDE
        self.panes.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)

    def mousePressEvent(self, event) -> None:
        handle = self.windowHandle()
        if event.button() == Qt.MouseButton.LeftButton and handle is not None:
            handle.startSystemMove()
        super().mousePressEvent(event)


    def eventFilter(self, obj, event) -> bool:
        if obj is self.source_edit and event.type() == QEvent.Type.KeyPress and self._handle_key(event, True):
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        if not self._handle_key(event, False):
            super().keyPressEvent(event)

    def _handle_key(self, event: QKeyEvent, in_source: bool) -> bool:
        """Esc e Ctrl+Enter valem na janela toda; Enter e Shift+Enter só no campo de origem."""
        mods = event.modifiers()
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif _is_enter(event) and mods & Qt.KeyboardModifier.ControlModifier:
            self.copy()
            self.close()
        elif not in_source or not _is_enter(event):
            return False
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            self.source_edit.textCursor().insertText("\n")
        else:
            self.translate_now()
        return True


    def _set_source_text(self, text: str) -> None:
        self._syncing = True
        self.source_edit.setPlainText(text)
        self._syncing = False
        self._debounce.stop()

    def _on_text_changed(self) -> None:
        if self._live and not self._syncing:
            self._debounce.start()

    def translate_now(self) -> None:
        self._debounce.stop()
        text, cut = clip(self.source_edit.toPlainText())
        self._show_error(None)
        self._translation = ""
        self._forget_detected()
        self._update_swap()
        if not text.strip():
            self._pending = None
            self.result_view.clear()
            self.status.clear()
            return
        self._live = True
        self.status.setText(CLIPPED if cut else "")
        self.result_view.setPlainText(LOADING)
        self._last_request = (text, self._source, self._target)
        self._pending = self.translator.translate(text, self._source, self._target)

    def _on_finished(self, request_id: int, result) -> None:
        if request_id != self._pending:
            return
        self._pending = None
        self._translation = result.text
        self.result_view.setPlainText(result.text)
        self._detected = result.detected if self._source == AUTO else None
        self._update_detected_label()
        self._update_swap()

    def _on_failed(self, request_id: int, kind: str) -> None:
        if request_id != self._pending:
            return
        self._pending = None
        self._translation = ""
        self._forget_detected()
        self._show_error(ERRORS.get(kind, ERRORS["refused"]), retry=kind != "format")
        self._update_swap()

    def _show_error(self, message: str | None, retry: bool = True) -> None:
        """Sem ``retry`` (resposta em formato novo), tentar de novo não adianta."""
        if message:
            self.result_view.setPlainText(message)
        self.retry_button.setVisible(bool(message) and retry)
        self.web_button.setVisible(bool(message))

    def _open_web(self) -> None:
        text, source, target = self._last_request or (self.source_edit.toPlainText(), self._source, self._target)
        QDesktopServices.openUrl(QUrl(web_url(text, source, target)))

    def copy(self) -> None:
        if self._translation:
            QGuiApplication.clipboard().setText(self._translation)


    def _on_language(self, box: QComboBox) -> None:
        if self._syncing or box.currentIndex() < 0:
            return
        code = box.currentData()
        if box is self.source_box:
            self._source = code
            self._forget_detected()
        else:
            self._target = code
        self._save_languages(code)
        self._update_swap()
        if self._live:
            self.translate_now()

    def swap(self) -> None:
        source = self._detected if self._source == AUTO else self._source
        if source not in CODES:
            return
        new_source, new_target = self._target, source
        self._source, self._target = new_source, new_target
        self._syncing = True
        self.source_box.setCurrentIndex(self.source_box.findData(new_source))
        self.target_box.setCurrentIndex(self.target_box.findData(new_target))
        self._syncing = False
        self._forget_detected()
        self._save_languages(new_target, new_source)
        if self._translation:
            self._set_source_text(self._translation)
        self._update_swap()
        if self._live:
            self.translate_now()

    def _forget_detected(self) -> None:
        self._detected = None
        self._update_detected_label()

    def _update_detected_label(self) -> None:
        index = self.source_box.findData(AUTO)
        if index < 0:
            return
        label = name_of(AUTO)
        if self._detected:
            label = f"{label}: {name_of(self._detected).lower()}"
        self.source_box.setItemText(index, label)
        if self.source_box.currentIndex() == index:
            self.source_box.setEditText(label)

    def _update_swap(self) -> None:
        self.swap_button.setEnabled(self._source != AUTO or self._detected in CODES)
        self.copy_button.setEnabled(bool(self._translation))


    def _on_pin(self, pinned: bool) -> None:
        self._save(translate_pinned=pinned)

    def _save_languages(self, *codes: str) -> None:
        recent = list(self.settings.translate_recent)
        for code in codes:
            recent = push_recent(recent, code)
        self._save(translate_source=self._source, translate_target=self._target, translate_recent=recent)

    def _save(self, **changes) -> None:
        if all(getattr(self.settings, k) == v for k, v in changes.items()):
            return
        self.settings = replace(self.settings, **changes)
        self._on_settings_changed(self.settings)
