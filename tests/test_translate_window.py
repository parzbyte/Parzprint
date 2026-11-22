import time

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout

from parzprint.settings import Settings
from parzprint.translate import window as window_mod
from parzprint.translate.google import Result
from parzprint.translate.window import TranslatorWindow, place_window
from tests.conftest import wait_until

ANCHOR = QRect(100, 100, 1, 1)


class FakeTranslator(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.requests: list[tuple[str, str, str]] = []
        self.ids: list[int] = []
        self._next = 0
        self.closed = False

    def translate(self, text, source, target):
        self._next += 1
        self.requests.append((text, source, target))
        self.ids.append(self._next)
        return self._next

    def shutdown(self):
        self.closed = True

    def answer(self, text, detected=None, request_id=None):
        self.finished.emit(request_id or self.ids[-1], Result(text, detected))

    def fail(self, kind, request_id=None):
        self.failed.emit(request_id or self.ids[-1], kind)


def make(qapp, **overrides):
    fake = FakeTranslator()
    saved: list[Settings] = []
    win = TranslatorWindow(fake, Settings(**overrides), saved.append)
    return win, fake, saved


def test_auto_translates_immediately(qapp):
    win, fake, _ = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    assert fake.requests == [("hello", "auto", "pt")]
    assert win.result_view.toPlainText() == "Traduzindo..."
    fake.answer("olá", "en")
    assert win.result_view.toPlainText() == "olá"
    assert "inglês" in win.source_box.currentText()
    assert win.source_box.currentText() == "Detectar idioma: inglês"
    win.close()


def test_clipboard_text_waits_for_enter(qapp):
    win, fake, _ = make(qapp)
    win.open("senha123", ANCHOR, auto=False)
    assert fake.requests == []
    assert "Aperte Enter" in win.status.text()
    assert win.source_edit.textCursor().selectedText() == "senha123"
    QTest.keyClick(win.source_edit, Qt.Key.Key_Return)
    assert fake.requests == [("senha123", "auto", "pt")]
    assert win.source_edit.toPlainText() == "senha123"
    win.close()


def test_shift_enter_breaks_line(qapp):
    win, fake, _ = make(qapp)
    win.open("", ANCHOR, auto=False)
    QTest.keyClicks(win.source_edit, "a")
    QTest.keyClick(win.source_edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(win.source_edit, "b")
    assert win.source_edit.toPlainText() == "a\nb"
    assert fake.requests == []
    win.close()


def test_edit_debounce_600ms(qapp):
    win, fake, _ = make(qapp)
    win.open("a", ANCHOR, auto=True)
    fake.answer("a")
    start = time.monotonic()
    for word in ("ab", "abc", "abcd"):
        win.source_edit.setPlainText(word)
    assert len(fake.requests) == 1
    assert not wait_until(lambda: len(fake.requests) > 1, timeout_s=0.4)
    assert wait_until(lambda: len(fake.requests) > 1, timeout_s=1)
    assert time.monotonic() - start >= 0.55
    wait_until(lambda: False, timeout_s=0.7)
    assert fake.requests[1:] == [("abcd", "auto", "pt")]
    win.close()


def test_edit_before_first_translation_does_not_translate(qapp):
    win, fake, _ = make(qapp)
    win.open("copiado", ANCHOR, auto=False)
    win.source_edit.setPlainText("outra coisa")
    assert not wait_until(lambda: fake.requests, timeout_s=0.8)
    win.close()


def test_only_latest_result_shown(qapp):
    win, fake, _ = make(qapp)
    win.open("one", ANCHOR, auto=True)
    old = fake.ids[-1]
    win.source_edit.setPlainText("two")
    QTest.keyClick(win.source_edit, Qt.Key.Key_Return)
    fake.answer("um", "en", request_id=old)
    assert win.result_view.toPlainText() == "Traduzindo..."
    fake.fail("network", request_id=old)
    assert win.result_view.toPlainText() == "Traduzindo..."
    fake.answer("dois", "en")
    assert win.result_view.toPlainText() == "dois"
    win.close()


def test_swap(qapp):
    win, fake, saved = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    assert not win.swap_button.isEnabled()
    fake.answer("olá", "en")
    assert win.swap_button.isEnabled()
    win.swap_button.click()
    assert win.source_box.currentData() == "pt"
    assert win.target_box.currentData() == "en"
    assert win.source_edit.toPlainText() == "olá"
    assert fake.requests[-1] == ("olá", "pt", "en")
    assert saved[-1].translate_source == "pt"
    assert saved[-1].translate_target == "en"
    win.close()


def test_errors_show_messages(qapp):
    messages = {
        "network": "Não consegui falar com o Google Tradutor. Confira a internet.",
        "refused": "O Google Tradutor recusou o pedido agora. Espere um pouco e tente de novo.",
        "format": "O Google Tradutor mudou o jeito de responder. Atualize o Parzprint.",
    }
    win, fake, _ = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    assert win.retry_button.isHidden()
    assert win.web_button.isHidden()
    for kind, message in messages.items():
        fake.fail(kind)
        assert win.result_view.toPlainText() == message
        assert not win.retry_button.isHidden()
        assert not win.web_button.isHidden()
        win.retry_button.click()
        assert win.retry_button.isHidden()
        assert fake.requests[-1] == ("hello", "auto", "pt")
    win.close()


def test_web_button_opens_google(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(window_mod.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    win, fake, _ = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    fake.fail("network")
    win.web_button.click()
    assert opened == ["https://translate.google.com/?sl=auto&tl=pt&text=hello&op=translate"]
    win.close()


def test_clip_warning(qapp):
    win, fake, _ = make(qapp)
    win.open("x" * 5001, ANCHOR, auto=True)
    assert len(fake.requests[0][0]) == 5000
    assert win.status.text() == "Traduzi só os primeiros 5.000 caracteres."
    win.close()


def test_reopen_reuses_window(qapp):
    win, fake, _ = make(qapp)
    win.open("first", ANCHOR, auto=True)
    first = win
    win.open("second", ANCHOR, auto=True)
    assert win is first
    assert win.isVisible()
    assert win.source_edit.toPlainText() == "second"
    assert fake.requests[-1] == ("second", "auto", "pt")
    win.close()


def test_language_change_saves_settings(qapp):
    win, fake, saved = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    win.target_box.setCurrentIndex(win.target_box.findData("en"))
    assert saved[-1].translate_target == "en"
    assert saved[-1].translate_recent == ["en"]
    assert win.settings is saved[-1]
    assert fake.requests[-1] == ("hello", "auto", "en")
    win.close()


def test_language_change_before_translation_waits(qapp):
    win, fake, saved = make(qapp)
    win.open("hello", ANCHOR, auto=False)
    win.source_box.setCurrentIndex(win.source_box.findData("en"))
    assert saved[-1].translate_source == "en"
    assert saved[-1].translate_recent == ["en"]
    assert fake.requests == []
    win.close()


def test_pin_keeps_open_on_deactivate(qapp):
    win, _, saved = make(qapp)
    win.open("hello", ANCHOR, auto=False)
    assert win.isVisible()
    QApplication.sendEvent(win, QEvent(QEvent.Type.WindowDeactivate))
    assert not win.isVisible()

    win.open("hello", ANCHOR, auto=False)
    win.pin_button.click()
    assert saved[-1].translate_pinned is True
    QApplication.sendEvent(win, QEvent(QEvent.Type.WindowDeactivate))
    assert win.isVisible()
    win.close()


def test_close_saves_size_and_pin(qapp):
    win, _, saved = make(qapp, translate_size=[700, 320], translate_pinned=True)
    win.open("hello", ANCHOR, auto=False)
    assert win.pin_button.isChecked()
    assert (win.width(), win.height()) == (700, 320)
    win.resize(500, 260)
    win.close()
    assert saved[-1].translate_size == [500, 260]
    assert saved[-1].translate_pinned is True


def test_layout_follows_width(qapp):
    win, _, _ = make(qapp)
    win.open("hello", ANCHOR, auto=False)
    win.resize(600, 300)
    assert wait_until(lambda: win.panes.direction() == QBoxLayout.Direction.LeftToRight)
    win.resize(400, 400)
    assert wait_until(lambda: win.panes.direction() == QBoxLayout.Direction.TopToBottom)
    win.close()


def test_ctrl_enter_copies_and_closes(qapp):
    win, fake, _ = make(qapp)
    win.open("hello", ANCHOR, auto=True)
    fake.answer("olá", "en")
    QTest.keyClick(win.source_edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text() == "olá"
    assert not win.isVisible()


def test_escape_closes(qapp):
    win, _, _ = make(qapp)
    win.open("hello", ANCHOR, auto=False)
    QTest.keyClick(win.source_edit, Qt.Key.Key_Escape)
    assert not win.isVisible()


def test_place_window():
    avail = QRect(0, 0, 1000, 800)
    size = QSize(300, 200)
    # cabe abaixo e à direita
    assert place_window(QRect(100, 100, 10, 20), size, avail) == QPoint(100, 126)
    # sem espaço abaixo, vai para cima
    assert place_window(QRect(100, 700, 10, 20), size, avail) == QPoint(100, 494)
    # preso no canto inferior direito
    assert place_window(QRect(950, 790, 1, 1), size, avail) == QPoint(700, 584)
    # área com deslocamento (segundo monitor) e ponto fora dela
    assert place_window(QRect(-50, -50, 1, 1), size, QRect(0, 40, 1000, 760)) == QPoint(0, 40)
