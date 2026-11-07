from parzprint.ocr.base import TextBlock
from parzprint.textpanel import TextSelectionModel

B = [TextBlock("a", 0, 0, 10, 10), TextBlock("b", 20, 0, 10, 10), TextBlock("c", 0, 20, 10, 10)]


def test_hit():
    m = TextSelectionModel(B)
    assert m.hit(5, 5) == 0
    assert m.hit(25, 5) == 1
    assert m.hit(50, 50) is None


def test_select_only_and_text():
    m = TextSelectionModel(B)
    m.select_only(1)
    assert m.selected_indices() == [1]
    assert m.selected_text() == "b"


def test_drag_selects_intersecting_in_reading_order():
    m = TextSelectionModel(B)
    m.select_range_by_drag((5, 5, 30, 20))
    assert m.selected_indices() == [0, 1, 2]
    assert m.selected_text() == "a\nb\nc"


def test_drag_with_negative_size_is_normalized():
    m = TextSelectionModel(B)
    m.select_range_by_drag((30, 8, -25, -6))
    assert m.selected_indices() == [0, 1]


def test_drag_replaces_previous_selection():
    m = TextSelectionModel(B)
    m.select_only(2)
    m.select_range_by_drag((0, 0, 5, 5))
    assert m.selected_indices() == [0]


def test_clear_and_empty_selected_text():
    m = TextSelectionModel(B)
    m.select_only(0)
    m.clear()
    assert m.selected_indices() == []
    assert m.selected_text() == ""


def test_all_text():
    assert TextSelectionModel(B).all_text() == "a\nb\nc"


def test_empty_model():
    m = TextSelectionModel([])
    assert m.all_text() == ""
    assert m.hit(0, 0) is None
