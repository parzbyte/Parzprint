"""Testes do editor numa janela Qt sem tela (offscreen)."""

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtTest import QTest

from parzprint.annotations import Point, Rect
from parzprint.capture import Monitor
from parzprint.editor import Editor
from parzprint.ocr.base import TextBlock
from parzprint.overlay import Mode, SelectionOverlay
from parzprint.toolbar import Tool


def near(px, rgb, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], rgb))


def make_editor(qapp, scale=1):
    img = Image.new("RGB", (400 * scale, 300 * scale), "white")
    ov = SelectionOverlay(Monitor(1, 0, 0, 400, 300, img))
    ov.sel = QRect(50, 50, 200, 150)
    ov.mode = Mode.SELECTED
    ov.locked = True
    ov.show()
    ed = Editor(ov)
    cancelled = []
    ov.cancelled.connect(lambda: cancelled.append(True))
    return ov, ed, cancelled


def start_text(ed, text):
    ed.side.buttons[Tool.TEXT].click()
    ed.press(QPointF(60, 60))
    ed._text_edit.setText(text)
    return ed._text_edit


def test_enter_confirms_text_without_closing(qapp):
    ov, ed, cancelled = make_editor(qapp)
    edit = start_text(ed, "ok")
    QTest.keyClick(edit, Qt.Key.Key_Return)
    assert len(ed.stack) == 1
    assert cancelled == []
    ov.close()


def test_escape_in_text_edit_cancels_only_the_text(qapp):
    ov, ed, cancelled = make_editor(qapp)
    edit = start_text(ed, "rascunho")
    QTest.keyClick(edit, Qt.Key.Key_Escape)
    assert len(ed.stack) == 0
    assert ed._text_edit is None
    assert cancelled == []
    ov.close()


def test_resize_keeps_annotations_on_their_content(qapp):
    ov, ed, _ = make_editor(qapp)
    # borda do retângulo no pixel (60, 60) do monitor
    ed.stack.add(Rect(Point(10, 10), Point(40, 40), "#E53935", width=3))
    ed._committed = None
    assert near(ed.composite().getpixel((10, 20)), (229, 57, 53))
    ov.sel = QRect(30, 50, 220, 150)  # alça esquerda puxada 20 px
    ov.selection_changed.emit(QRect(ov.sel))
    out = ed.composite()
    assert near(out.getpixel((30, 20)), (229, 57, 53))  # ainda no pixel 60 do monitor
    assert out.getpixel((10, 20))[:3] == (255, 255, 255)
    ov.close()


def test_resize_keeps_annotations_at_scale_2(qapp):
    ov, ed, _ = make_editor(qapp, scale=2)
    ed.stack.add(Rect(Point(20, 20), Point(80, 80), "#000000", width=3))
    ed._committed = None
    ov.sel = QRect(40, 50, 210, 150)  # 10 px lógicos = 20 px físicos
    ov.selection_changed.emit(QRect(ov.sel))
    assert near(ed.composite().getpixel((40, 40)), (0, 0, 0))
    ov.close()


def test_ctrl_c_in_text_mode_without_selection_keeps_capture(qapp):
    ov, ed, cancelled = make_editor(qapp)
    ed._ocr_blocks = [TextBlock("olá", 5, 5, 30, 10)]
    ed._ensure_panel()
    ed._open_panel()
    assert ed.text_mode
    QTest.keyClick(ov, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert cancelled == []
    ov.close()


def test_wheel_changes_size_of_current_tool(qapp):
    ov, ed, _ = make_editor(qapp)
    ed.side.buttons[Tool.ARROW].click()
    start = ed.sizes[Tool.ARROW]
    assert ed.wheel(120)
    assert ed.sizes[Tool.ARROW] == start + 1
    ed.wheel(-120)
    ed.wheel(-120)
    assert ed.sizes[Tool.ARROW] == start - 1
    ed.press(QPointF(60, 60))
    ed.move(QPointF(150, 120))
    ed.release(QPointF(150, 120))
    assert ed.stack.items()[-1].width == start - 1
    ov.close()


def test_wheel_size_is_clamped_and_per_tool(qapp):
    ov, ed, _ = make_editor(qapp)
    ed.side.buttons[Tool.PENCIL].click()
    for _ in range(100):
        ed.wheel(-120)
    assert ed.sizes[Tool.PENCIL] == 1
    ed.side.buttons[Tool.MARKER].click()
    marker = ed.sizes[Tool.MARKER]
    ed.wheel(120)
    assert ed.sizes[Tool.MARKER] > marker
    assert ed.sizes[Tool.PENCIL] == 1
    ov.close()


def test_wheel_without_tool_does_nothing(qapp):
    ov, ed, _ = make_editor(qapp)
    before = dict(ed.sizes)
    assert not ed.wheel(120)
    assert ed.sizes == before
    ov.close()


def test_wheel_resizes_text_being_typed(qapp):
    ov, ed, _ = make_editor(qapp)
    edit = start_text(ed, "oi")
    size = ed.sizes[Tool.TEXT]
    ed.wheel(120)
    assert edit.font().pixelSize() == ed.sizes[Tool.TEXT] > size
    QTest.keyClick(edit, Qt.Key.Key_Return)
    assert ed.stack.items()[-1].size == ed.sizes[Tool.TEXT]
    ov.close()


LENS_BLOCKS = [TextBlock("olá mundo", 10, 10, 90, 12), TextBlock("segunda", 10, 30, 70, 12)]


def open_text_mode(qapp):
    ov, ed, cancelled = make_editor(qapp)
    ed._ocr_blocks = list(LENS_BLOCKS)
    ed._ensure_panel()
    ed._open_panel()
    return ov, ed, cancelled


def test_drag_over_image_selects_continuous_text(qapp):
    ov, ed, _ = open_text_mode(qapp)
    # sel começa em (50, 50): ponto da imagem (x, y) fica em (50 + x, 50 + y)
    ed.press(QPointF(58, 66))
    ed.move(QPointF(140, 86))
    ed.release(QPointF(140, 86))
    assert ed.layout.selected_text() == "olá mundo\nsegunda"
    assert ed.panel.selected_text() == "olá mundo\nsegunda"
    QTest.keyClick(ov, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    from PySide6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == "olá mundo\nsegunda"
    ov.close()


def test_double_click_selects_word_and_chip_copies(qapp):
    ov, ed, _ = open_text_mode(qapp)
    assert ed.double_click(QPointF(146, 66))
    assert ed.layout.selected_text() == "mundo"
    assert ed.copy_chip.isVisible()
    ed.copy_chip.click()
    from PySide6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == "mundo"
    ov.close()


def test_click_without_drag_clears_selection(qapp):
    ov, ed, _ = open_text_mode(qapp)
    ed.layout.select_all()
    ed.press(QPointF(70, 66))
    ed.release(QPointF(70, 66))
    assert not ed.layout.has_selection()
    assert not ed.copy_chip.isVisible()
    ov.close()


def test_ctrl_a_selects_all_text(qapp):
    ov, ed, _ = open_text_mode(qapp)
    QTest.keyClick(ov, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert ed.layout.selected_text() == "olá mundo\nsegunda"
    ov.close()


def test_selecting_in_panel_highlights_image(qapp):
    ov, ed, _ = open_text_mode(qapp)
    ed.panel.set_selection(0, 0)
    from PySide6.QtGui import QTextCursor

    c = ed.panel.edit.textCursor()
    c.setPosition(4)
    c.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
    ed.panel.edit.setTextCursor(c)
    assert ed.layout.selection == (4, 9)
    ov.close()


def _move_mouse(ov, x, y, buttons=Qt.MouseButton.NoButton):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent

    pos = QPointF(x, y)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove, pos, QPointF(ov.mapToGlobal(QPoint(x, y))),
        Qt.MouseButton.NoButton, buttons, Qt.KeyboardModifier.NoModifier,
    )
    ov.mouseMoveEvent(ev)


def test_text_mode_shows_insertion_cursor(qapp):
    ov, ed, _ = open_text_mode(qapp)
    ov.setCursor(Qt.CursorShape.CrossCursor)
    _move_mouse(ov, 200, 180)  # dentro da seleção, longe das linhas de texto
    assert ov.cursor().shape() == Qt.CursorShape.IBeamCursor
    _move_mouse(ov, 70, 66)  # sobre o texto
    assert ov.cursor().shape() == Qt.CursorShape.IBeamCursor
    ov.close()


def test_insertion_cursor_while_dragging_text(qapp):
    ov, ed, _ = open_text_mode(qapp)
    ov.setCursor(Qt.CursorShape.CrossCursor)
    ed.press(QPointF(60, 66))
    _move_mouse(ov, 120, 86, Qt.MouseButton.LeftButton)
    assert ov.cursor().shape() == Qt.CursorShape.IBeamCursor
    ov.close()


def _clipboard():
    from PySide6.QtWidgets import QApplication

    return QApplication.clipboard().text()


def test_copy_all_from_panel_closes_capture(qapp):
    ov, ed, cancelled = open_text_mode(qapp)
    ed.panel.copy_all_button.click()
    assert _clipboard() == "olá mundo\nsegunda"
    assert cancelled == [True]


def test_copy_selection_from_panel_closes_capture(qapp):
    ov, ed, cancelled = open_text_mode(qapp)
    ed.layout.select(4, 9)
    ed._after_selection()
    ed.panel.copy_sel_button.click()
    assert _clipboard() == "mundo"
    assert cancelled == [True]


def test_floating_copy_button_closes_capture(qapp):
    ov, ed, cancelled = open_text_mode(qapp)
    ed.double_click(QPointF(146, 66))
    ed.copy_chip.click()
    assert _clipboard() == "mundo"
    assert cancelled == [True]


def test_ctrl_c_with_text_selected_closes_capture(qapp):
    ov, ed, cancelled = open_text_mode(qapp)
    ed.layout.select_all()
    QTest.keyClick(ov, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert _clipboard() == "olá mundo\nsegunda"
    assert cancelled == [True]


def test_click_without_drag_selects_whole_monitor(qapp):
    img = Image.new("RGB", (400, 300), "white")
    ov = SelectionOverlay(Monitor(1, 0, 0, 400, 300, img))
    ov.show()
    got = []
    ov.selected.connect(got.append)
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 100))
    assert ov.sel == ov.screen_rect() and got == [QRect(0, 0, 400, 300)]
    ov.close()


def test_record_button_emits_area_and_items(qapp, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    ov, ed, cancelled = make_editor(qapp)
    r = Rect(Point(1, 1), Point(9, 9), "#000000", 3)
    ed.stack.add(r)
    got = []
    ed.record_requested.connect(lambda mon, area, items: got.append((mon, area, items)))
    ed.bottom.buttons["record"].click()
    assert got and got[0][0] is ov.monitor and got[0][1] == QRect(50, 50, 200, 150) and got[0][2] == [r]
    assert cancelled == [True]


def test_record_button_hidden_off_windows(qapp, monkeypatch):
    import sys

    from parzprint.toolbar import BottomToolbar

    monkeypatch.setattr(sys, "platform", "linux")
    bar = BottomToolbar(None)
    assert "record" not in bar.buttons
