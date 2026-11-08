from parzprint.colordialog import from_colorref, to_colorref


def test_colorref_roundtrip():
    assert to_colorref("#E53935") == 0x003539E5
    assert from_colorref(0x003539E5) == "#E53935"
    assert from_colorref(to_colorref("#1E88E5")) == "#1E88E5"


def test_colorref_lowercase_input():
    assert to_colorref("#ffffff") == 0x00FFFFFF
