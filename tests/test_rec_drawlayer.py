import sys

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from parzprint.annotations import Arrow, Point, Rect
from parzprint.drawing import DEFAULT_SIZES, extend_shape, is_empty, new_shape, step_size
from parzprint.recording.drawlayer import DrawLayer
from parzprint.recording.exclude import exclude_from_capture
from parzprint.toolbar import Tool


def test_shape_tool_creates_arrow_with_size():
    a = new_shape(Tool.ARROW, Point(1, 1), "#E53935", 12)
    assert isinstance(a, Arrow) and a.width == 12
    extend_shape(a, Point(50, 20))
    assert a.end == Point(50, 20) and not is_empty(a)
    assert is_empty(new_shape(Tool.LINE, Point(1, 1), "#000000", 3))
    assert new_shape(Tool.TEXT, Point(1, 1), "#000000", 3) is None


def test_step_size_limits():
    assert step_size(Tool.PENCIL, 1, -1) == 1
    assert step_size(Tool.MARKER, DEFAULT_SIZES[Tool.MARKER], 1) == DEFAULT_SIZES[Tool.MARKER] + 2
    assert step_size(Tool.ARROW, 30, 1) == 30


def _layer(qapp, items=None):
    layer = DrawLayer(QRect(100, 100, 400, 300), items or [], scale=1.0)
    layer.show()
    return layer


def test_drawlayer_starts_with_editor_items(qapp):
    r = Rect(Point(10, 10), Point(40, 40), "#E53935", 3)
    layer = _layer(qapp, [r])
    assert layer.stack.items() == [r]
    layer.close()


def test_drawing_in_draw_mode_adds_shape(qapp):
    layer = _layer(qapp)
    layer.set_draw_mode(True)
    layer.toolbar.buttons[Tool.RECT].click()
    layer.press(QPointF(10, 10))
    layer.move(QPointF(80, 60))
    layer.release(QPointF(80, 60))
    assert len(layer.stack) == 1 and isinstance(layer.stack.items()[0], Rect)
    layer.close()


def test_no_drawing_outside_draw_mode(qapp):
    layer = _layer(qapp)
    layer.tool = Tool.RECT
    assert not layer.press(QPointF(10, 10))
    layer.close()


def test_clear_removes_all(qapp):
    layer = _layer(qapp, [Rect(Point(1, 1), Point(9, 9), "#000000", 3)])
    layer.set_draw_mode(True)
    layer.toolbar.clear_button.click()
    assert len(layer.stack) == 0
    layer.close()


def test_draw_mode_toggles_toolbar_and_input(qapp):
    layer = _layer(qapp)
    seen = []
    layer.draw_mode_changed.connect(seen.append)
    layer.set_draw_mode(True)
    assert layer.toolbar.isVisible() and not layer.passes_clicks()
    layer.set_draw_mode(False)
    assert not layer.toolbar.isVisible() and layer.passes_clicks()
    assert seen == [True, False]
    layer.close()


def test_escape_leaves_draw_mode(qapp):
    layer = _layer(qapp)
    layer.set_draw_mode(True)
    QTest.keyClick(layer, Qt.Key.Key_Escape)
    assert not layer.draw_mode
    layer.close()


def test_wheel_changes_size_in_draw_mode(qapp):
    layer = _layer(qapp)
    layer.set_draw_mode(True)
    assert layer.tool is Tool.ARROW  # já entra com a seta escolhida
    before = layer.sizes[Tool.ARROW]
    layer.wheel(120)
    assert layer.sizes[Tool.ARROW] == before + 1
    layer.close()


def test_exclude_from_capture_returns_bool(qapp):
    w = QWidget()
    w.show()
    assert isinstance(exclude_from_capture(w), bool)
    if sys.platform != "win32":
        assert exclude_from_capture(w) is False
    w.close()
