from parzprint.ocr.base import TextBlock
from parzprint.textpanel import TextLayout

# medida uniforme: cada caractere tem 1 unidade, esticada para a largura do bloco
B = [TextBlock("olá mundo", 0, 0, 90, 10), TextBlock("segunda", 0, 20, 70, 10)]


def test_text_joins_lines():
    assert TextLayout(B).text == "olá mundo\nsegunda"


def test_position_at_inside_lines():
    t = TextLayout(B)
    assert t.position_at(0, 5) == 0
    assert t.position_at(31, 5) == 3
    assert t.position_at(14, 25) == 11  # "s|egunda"


def test_position_at_clamps_to_line_ends_and_nearest_line():
    t = TextLayout(B)
    assert t.position_at(500, 5) == 9  # fim da primeira linha
    assert t.position_at(-50, 25) == 10  # começo da segunda
    assert t.position_at(30, 300) == 13  # abaixo de tudo: última linha
    assert t.position_at(30, -40) == 3  # acima de tudo: primeira linha


def test_select_partial_across_lines():
    t = TextLayout(B)
    t.select(2, 13)
    assert t.selected_text() == "á mundo\nseg"
    t.select(13, 2)  # arrastar de trás para frente dá o mesmo trecho
    assert t.selected_text() == "á mundo\nseg"


def test_selection_rects_follow_characters():
    t = TextLayout(B)
    t.select(3, 13)
    assert t.selection_rects() == [(30, 0, 90, 10), (0, 20, 30, 30)]


def test_word_at():
    t = TextLayout(B)
    assert t.word_at(5) == (4, 9)
    assert t.text[slice(*t.word_at(12))] == "segunda"


def test_select_all_and_clear():
    t = TextLayout(B)
    t.select_all()
    assert t.selected_text() == "olá mundo\nsegunda"
    t.clear()
    assert t.selected_text() == ""
    assert t.selection_rects() == []


def test_measure_function_shapes_edges():
    # "iW": 'i' estreito, 'W' largo -> a fronteira fica perto do começo
    t = TextLayout([TextBlock("iW", 0, 0, 40, 10)], measure=lambda s: sum(1 if c == "i" else 3 for c in s))
    assert t.position_at(9, 5) == 1
    assert t.position_at(12, 5) == 1
    assert t.position_at(35, 5) == 2


def test_empty_layout():
    t = TextLayout([])
    assert t.text == ""
    assert t.position_at(10, 10) == 0
    assert t.selection_rects() == []
