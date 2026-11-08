"""Testes do editor numa janela Qt sem tela (offscreen)."""

from PIL import Image
from PySide6.QtCore import QPointF, QRect, Qt
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
