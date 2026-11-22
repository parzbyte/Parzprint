import json
import sys

from parzprint.settings import (
    Settings,
    hotkey_conflict,
    is_valid_hotkey,
    load_settings,
    save_settings,
)


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


def test_recording_defaults():
    s = Settings()
    assert (s.rec_resolution, s.rec_fps, s.rec_quality) == ("original", 30, "media")
    assert s.rec_compress and s.rec_countdown and s.system_audio
    assert s.mic_mode == "always" and s.mic_device == "" and s.ptt_hotkey == "Ctrl+Alt+Space"
    assert s.video_dir.endswith("Parzprint")


def test_invalid_recording_values_fall_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"rec_fps": 60, "rec_resolution": "4k", "rec_quality": "x", "mic_mode": "y",
                             "ptt_hotkey": "Ctrl+", "rec_compress": "sim", "mic_device": 5}), encoding="utf-8")
    s = load_settings(p)
    assert (s.rec_fps, s.rec_resolution, s.rec_quality, s.mic_mode) == (30, "original", "media", "always")
    assert s.ptt_hotkey == "Ctrl+Alt+Space" and s.rec_compress is True and s.mic_device == ""


def test_recording_values_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = Settings(rec_fps=15, rec_resolution="720", rec_quality="leve", mic_mode="ptt", mic_device="abc", system_audio=False)
    save_settings(s, p)
    assert load_settings(p) == s


def test_fps_rejects_bool(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"rec_fps": True}), encoding="utf-8")
    assert load_settings(p).rec_fps == 30


def test_translate_defaults():
    from parzprint import settings as mod

    assert mod.DEFAULT_TRANSLATE_HOTKEY == ("Ctrl+Alt+T" if sys.platform == "win32" else "Ctrl+Alt+Y")
    s = Settings()
    assert s.translate_source == "auto" and s.translate_target == "pt"
    assert s.translate_grab_selection is True and s.translate_pinned is False
    assert s.translate_recent == [] and s.translate_size == [640, 300]
    s.translate_recent.append("en")
    assert Settings().translate_recent == []


def test_translate_invalid_values_fall_back(tmp_path):
    p = tmp_path / "s.json"
    for bad in ("auto", "xx"):
        p.write_text(json.dumps({"translate_target": bad}), encoding="utf-8")
        assert load_settings(p).translate_target == "pt"
    p.write_text(json.dumps({"translate_size": [10, "a"], "translate_recent": "en"}), encoding="utf-8")
    s = load_settings(p)
    assert s.translate_size == [640, 300] and s.translate_recent == []
    p.write_text(json.dumps({"translate_size": [300, 160]}), encoding="utf-8")
    assert load_settings(p).translate_size == [640, 300]
    p.write_text(json.dumps({"translate_size": [320, 160], "translate_recent": ["en", "xx"]}), encoding="utf-8")
    s = load_settings(p)
    assert s.translate_size == [320, 160] and s.translate_recent == []
    p.write_text(json.dumps({"translate_recent": ["en", "ja"], "translate_source": "xx"}), encoding="utf-8")
    s = load_settings(p)
    assert s.translate_recent == ["en", "ja"] and s.translate_source == "auto"


def test_hotkey_conflict():
    s = Settings()
    assert hotkey_conflict(s) is None
    s.translate_hotkey = s.hotkey
    assert hotkey_conflict(s)
    s.translate_hotkey = "Ctrl+Alt+Q"
    s.ptt_hotkey = s.hotkey
    assert hotkey_conflict(s)
