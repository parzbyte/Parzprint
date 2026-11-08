from types import SimpleNamespace

import pytest
from PIL import Image

from parzprint.ocr import OcrError, get_engine
from parzprint.ocr.base import TextBlock, join_text, reading_order
from parzprint.ocr.fake import FakeEngine
from parzprint.ocr.indra import IndraEngine


def test_reading_order_sorts_lines_then_columns():
    b = [TextBlock("c", 0, 40, 10, 10), TextBlock("b", 50, 0, 10, 10), TextBlock("a", 0, 2, 10, 10)]
    assert [t.text for t in reading_order(b)] == ["a", "b", "c"]


def test_reading_order_empty():
    assert reading_order([]) == []


def test_join_text():
    assert join_text([TextBlock("olá", 0, 0, 1, 1), TextBlock("mundo", 0, 20, 1, 1)]) == "olá\nmundo"


def test_fake_engine_returns_given_blocks():
    blocks = [TextBlock("x", 1, 2, 3, 4)]
    assert FakeEngine(blocks).recognize(Image.new("RGB", (5, 5))) == blocks


def test_get_engine_unknown_raises():
    with pytest.raises(OcrError):
        get_engine("x")


def test_get_engine_indra():
    assert isinstance(get_engine("indra"), IndraEngine)


def _page(*lines):
    return SimpleNamespace(lines=[SimpleNamespace(box=list(b), text=t, conf=0.99) for t, b in lines])


def test_indra_blocks_relative_to_image(monkeypatch):
    eng = IndraEngine()
    monkeypatch.setattr(eng, "_run_model", lambda gray: _page(("abc", [10.4, 20.0, 110.0, 60.2])))
    assert eng.recognize(Image.new("RGB", (200, 100))) == [TextBlock("abc", 10, 20, 100, 40)]


def test_indra_passes_grayscale_uint8(monkeypatch):
    eng = IndraEngine()
    seen = {}

    def run(gray):
        seen["shape"], seen["dtype"] = gray.shape, str(gray.dtype)
        return _page()

    monkeypatch.setattr(eng, "_run_model", run)
    eng.recognize(Image.new("RGBA", (30, 20)))
    assert seen == {"shape": (20, 30), "dtype": "uint8"}


def test_indra_drops_empty_lines_and_clamps(monkeypatch):
    eng = IndraEngine()
    monkeypatch.setattr(
        eng, "_run_model", lambda g: _page(("  ", [0, 0, 5, 5]), ("ok", [-3.0, -1.0, 250.0, 30.0]))
    )
    assert eng.recognize(Image.new("RGB", (200, 100))) == [TextBlock("ok", 0, 0, 200, 30)]


def test_indra_wraps_library_errors(monkeypatch):
    eng = IndraEngine()

    def boom(gray):
        raise RuntimeError("falhou")

    monkeypatch.setattr(eng, "_run_model", boom)
    with pytest.raises(OcrError, match="falhou"):
        eng.recognize(Image.new("RGB", (5, 5)))


def test_get_engine_reuses_instance():
    assert get_engine("indra") is get_engine("indra")


def test_is_model_cached_uses_indra_file_patterns(monkeypatch):
    import huggingface_hub

    from parzprint.ocr.indra import is_model_cached

    seen = {}

    def fake(repo, **kw):
        seen.update(kw)
        return "/x"

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake)
    assert is_model_cached()
    assert seen["local_files_only"] is True
    assert "*.onnx" in seen["allow_patterns"]


def test_indra_runs_upright_only(monkeypatch):
    eng = IndraEngine()
    seen = {}

    class FakeConv:
        def ocr(self, gray, turn=True):
            seen["turn"] = turn
            return _page()

    monkeypatch.setattr(eng, "_load", lambda: FakeConv())
    eng.recognize(Image.new("RGB", (10, 10)))
    assert seen["turn"] is False


def _fake_bundle(tmp_path):
    d = tmp_path / "indra"
    d.mkdir()
    for f in ("det.onnx", "rec.onnx", "order.onnx", "meta.json"):
        (d / f).write_bytes(b"x")
    return d


def test_bundled_model_dir_found(monkeypatch, tmp_path):
    import parzprint.ocr.indra as indra_mod

    d = _fake_bundle(tmp_path)
    monkeypatch.setattr(indra_mod, "BUNDLED_MODEL_DIR", d)
    assert indra_mod.bundled_model_dir() == d
    monkeypatch.setattr(indra_mod, "BUNDLED_MODEL_DIR", tmp_path / "nada")
    assert indra_mod.bundled_model_dir() is None


def test_bundled_model_counts_as_cached_without_network(monkeypatch, tmp_path):
    import huggingface_hub

    import parzprint.ocr.indra as indra_mod

    monkeypatch.setattr(indra_mod, "BUNDLED_MODEL_DIR", _fake_bundle(tmp_path))

    def no_network(*a, **k):
        raise AssertionError("não deveria consultar o Hugging Face")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", no_network)
    assert indra_mod.is_model_cached()


def test_engine_loads_from_bundled_dir(monkeypatch, tmp_path):
    import indra_ocr

    import parzprint.ocr.indra as indra_mod

    d = _fake_bundle(tmp_path)
    monkeypatch.setattr(indra_mod, "BUNDLED_MODEL_DIR", d)
    seen = {}
    monkeypatch.setattr(indra_ocr, "load", lambda path=None, **kw: seen.setdefault("path", path) or object())
    IndraEngine()._load()
    assert seen["path"] == str(d)
