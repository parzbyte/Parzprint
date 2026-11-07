from PySide6.QtCore import QPoint, QRect, QSize

from parzprint.geometry import GAP, normalize_rect, place_panel, place_toolbars

SCREEN = QRect(0, 0, 1000, 800)
SIDE = QSize(40, 300)
BOTTOM = QSize(200, 40)


def test_normalize_rect():
    assert normalize_rect(50, 50, 10, 10) == (10, 10, 40, 40)
    assert normalize_rect(10, 10, 50, 50) == (10, 10, 40, 40)
    assert normalize_rect(50, 10, 10, 50) == (10, 10, 40, 40)
    assert normalize_rect(5, 5, 5, 5) == (5, 5, 0, 0)


def test_place_toolbars_prefers_right_and_below():
    sel = QRect(100, 100, 300, 300)
    side, bottom = place_toolbars(sel, SCREEN, SIDE, BOTTOM)
    assert side == QPoint(400 + GAP, 100)
    assert bottom == QPoint(400 - BOTTOM.width(), 400 + GAP)


def test_place_toolbars_flips_when_near_edge():
    sel = QRect(600, 450, 380, 340)  # colada à direita e embaixo
    side, bottom = place_toolbars(sel, SCREEN, SIDE, BOTTOM)
    assert side.x() == 600 - GAP - SIDE.width()
    assert bottom.y() == 450 - GAP - BOTTOM.height()


def test_place_toolbars_inside_when_selection_is_full_screen():
    side, bottom = place_toolbars(SCREEN, SCREEN, SIDE, BOTTOM)
    assert SCREEN.contains(QRect(side, SIDE))
    assert SCREEN.contains(QRect(bottom, BOTTOM))


def test_place_toolbars_clamps_vertically():
    sel = QRect(100, 700, 100, 50)
    side, _ = place_toolbars(sel, SCREEN, SIDE, BOTTOM)
    assert side.y() + SIDE.height() <= SCREEN.bottom() + 1


def test_place_panel_right_of_avoid_then_left():
    sel = QRect(100, 100, 300, 300)
    avoid = QRect(406, 100, 40, 300)
    assert place_panel(sel, SCREEN, QSize(300, 400), avoid) == QPoint(446 + GAP, 100)
    sel2 = QRect(500, 100, 300, 300)
    p = place_panel(sel2, SCREEN, QSize(300, 400), QRect(806, 100, 40, 300))
    assert p.x() == 500 - GAP - 300


def test_place_panel_stays_on_screen():
    p = place_panel(QRect(0, 0, 1000, 800), SCREEN, QSize(300, 400), QRect(950, 0, 40, 300))
    assert SCREEN.contains(QRect(p, QSize(300, 400)))
