"""Recompressão com x264 (qualidade constante, como o HandBrake) e finalização do arquivo."""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_X264 = {"alta": ("20", "slow"), "media": ("23", "medium"), "leve": ("27", "medium")}


def x264_args(src: Path, dst: Path, quality: str) -> list[str]:
    crf, preset = _X264.get(quality, _X264["media"])
    return [
        "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
        "-c:v", "libx264", "-crf", crf, "-preset", preset, "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(dst),
    ]


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _default_runner(args: list[str], register=None) -> int:
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen([ffmpeg_exe(), *args], creationflags=flags,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if register is not None:
        register(proc)
    return proc.wait()


def _free_name(final: Path) -> Path:
    if not final.exists():
        return final
    n = 2
    while True:
        cand = final.with_name(f"{final.stem} ({n}){final.suffix}")
        if not cand.exists():
            return cand
        n += 1


def finalize(
    temp: Path, final: Path, compress: bool, quality: str,
    runner: Callable[..., int] | None = None, register=None,
) -> Path:
    """Transforma o arquivo gravado no vídeo final; nunca perde a gravação.

    Com ``compress``, recomprime com x264 e só usa o resultado se deu certo e ficou menor.
    """
    final = _free_name(final)
    if compress:
        work = final.with_name(final.stem + ".comprimindo.mp4")
        try:
            run = runner or _default_runner
            args = x264_args(temp, work, quality)
            code = run(args) if register is None else run(args, register=register)
        except Exception:  # noqa: BLE001
            code = -1
        if code == 0 and work.exists() and 0 < work.stat().st_size < temp.stat().st_size:
            work.replace(final)
            temp.unlink(missing_ok=True)
            return final
        work.unlink(missing_ok=True)
    temp.replace(final)
    return final


class CompressWorker(QObject):
    """Roda ``finalize`` numa thread daemon e avisa quando termina."""

    started = Signal(object)  # Path final pretendido
    done = Signal(object, int)  # Path final, tamanho em bytes
    failed = Signal(str)

    def __init__(self, temp: Path, final: Path, compress: bool, quality: str, runner=None):
        super().__init__(None)
        self._args = (temp, final, compress, quality)
        self._runner = runner
        self._proc = None
        self._thread = threading.Thread(target=self._run, name="parzprint-compress", daemon=True)

    def start(self) -> None:
        _running.add(self)
        self.started.emit(self._args[1])
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread.is_alive()

    def _register(self, proc) -> None:
        self._proc = proc

    def abort(self, timeout: float = 5.0) -> None:
        """Interrompe a compressão (ao fechar o app); o vídeo original fica com o nome final."""
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:  # noqa: BLE001
                pass
        self._thread.join(timeout)

    def _run(self) -> None:
        try:
            out = finalize(*self._args, runner=self._runner, register=self._register)
            self.done.emit(out, out.stat().st_size)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        finally:
            _running.discard(self)


_running: set[CompressWorker] = set()


def running_workers() -> list[CompressWorker]:
    return list(_running)
