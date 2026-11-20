from pathlib import Path

from parzprint.recording.compress import finalize, x264_args


def test_x264_args_media():
    a = x264_args(Path("in.mp4"), Path("out.mp4"), "media")
    assert a[a.index("-crf") + 1] == "23" and a[a.index("-preset") + 1] == "medium"
    assert a[a.index("-c:a") + 1] == "copy" and a[a.index("-pix_fmt") + 1] == "yuv420p"
    assert "+faststart" in a and "-y" in a and a[-1] == "out.mp4"


def test_x264_args_alta_and_leve():
    a = x264_args(Path("i"), Path("o"), "alta")
    assert a[a.index("-crf") + 1] == "20" and a[a.index("-preset") + 1] == "slow"
    b = x264_args(Path("i"), Path("o"), "leve")
    assert b[b.index("-crf") + 1] == "27"


def _temp(tmp_path, size=1000):
    t = tmp_path / "v.gravando.mp4"
    t.write_bytes(b"o" * size)
    return t


def _runner(size, code=0):
    def run(args):
        if code == 0:
            Path(args[-1]).write_bytes(b"c" * size)
        return code
    return run


def test_finalize_uses_smaller_compressed(tmp_path):
    t, final = _temp(tmp_path), tmp_path / "v.mp4"
    out = finalize(t, final, True, "media", runner=_runner(400))
    assert out == final and final.stat().st_size == 400 and not t.exists()
    assert not list(tmp_path.glob("*.comprimindo.mp4"))


def test_finalize_keeps_original_when_compressed_is_bigger(tmp_path):
    t, final = _temp(tmp_path), tmp_path / "v.mp4"
    finalize(t, final, True, "media", runner=_runner(2000))
    assert final.stat().st_size == 1000 and not list(tmp_path.glob("*.comprimindo.mp4"))


def test_finalize_keeps_original_when_compression_fails(tmp_path):
    t, final = _temp(tmp_path), tmp_path / "v.mp4"
    finalize(t, final, True, "media", runner=_runner(0, code=1))
    assert final.read_bytes() == b"o" * 1000


def test_finalize_keeps_original_when_runner_raises(tmp_path):
    t, final = _temp(tmp_path), tmp_path / "v.mp4"

    def boom(args):
        raise OSError("sem ffmpeg")

    finalize(t, final, True, "media", runner=boom)
    assert final.stat().st_size == 1000


def test_finalize_without_compress_renames(tmp_path):
    t, final = _temp(tmp_path), tmp_path / "v.mp4"
    called = []
    assert finalize(t, final, False, "media", runner=lambda a: called.append(a) or 0) == final
    assert final.exists() and not t.exists() and called == []


def test_finalize_never_overwrites(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"x")
    t = _temp(tmp_path)
    out = finalize(t, tmp_path / "v.mp4", False, "media")
    assert out == tmp_path / "v (2).mp4" and (tmp_path / "v.mp4").read_bytes() == b"x"
