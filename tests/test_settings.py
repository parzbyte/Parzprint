import json

from parzprint.settings import Settings, is_valid_hotkey, load_settings, save_settings


def test_defaults():
    s = Settings()
    assert s.hotkey == "Ctrl+Shift+S"
    assert s.image_format == "PNG"
    assert s.autostart is True
    assert s.ocr_engine == "indra"
    assert s.save_dir


def test_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    save_settings(Settings(hotkey="Alt+P", image_format="JPG"), p)
    assert load_settings(p) == Settings(hotkey="Alt+P", image_format="JPG")


def test_missing_file_returns_defaults(tmp_path):
    assert load_settings(tmp_path / "nope.json") == Settings()


def test_corrupt_file_returns_defaults_and_rewrites(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{oops", encoding="utf-8")
    assert load_settings(p) == Settings()
    assert json.loads(p.read_text(encoding="utf-8"))["hotkey"] == "Ctrl+Shift+S"


def test_invalid_hotkey_falls_back_to_default(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"hotkey": "Ctrl+", "image_format": "JPG"}), encoding="utf-8")
    s = load_settings(p)
    assert s.hotkey == "Ctrl+Shift+S"
    assert s.image_format == "JPG"


def test_unknown_format_falls_back_to_png(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"image_format": "GIF"}), encoding="utf-8")
    assert load_settings(p).image_format == "PNG"


def test_wrong_types_fall_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"autostart": "yes", "save_dir": 3, "extra": 1}), encoding="utf-8")
    s = load_settings(p)
    assert s.autostart is True
    assert s.save_dir == Settings().save_dir


def test_is_valid_hotkey():
    assert is_valid_hotkey("Ctrl+Shift+S")
    assert is_valid_hotkey("Win+Print")
    assert is_valid_hotkey("Alt+F2")
    assert not is_valid_hotkey("S")
    assert not is_valid_hotkey("Ctrl+")
    assert not is_valid_hotkey("")
    assert not is_valid_hotkey("Ctrl+Shift")
    assert not is_valid_hotkey("Foo+S")
