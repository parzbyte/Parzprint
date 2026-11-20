"""Sessão de gravação: contagem, captura, pausa, fim, e entrega do arquivo final."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QTimer, QUrl, Signal

from ..capture import Monitor
from ..settings import Settings
from .clock import RecordingClock
from .plan import crop_box, output_size, temp_path, video_filename

COUNTDOWN_SECONDS = 3
STOP_TIMEOUT_MS = 10_000  # se o gravador não confirmar o fim nesse tempo, fecha mesmo assim


class AudioQueue:
    """Blocos de áudio recusados pelo gravador ficam na fila e saem na ordem, sem buracos."""

    def __init__(self, send):
        self._send = send
        self._items: list[tuple[bytes, int]] = []

    def push(self, data: bytes, us: int) -> None:
        self._items.append((data, us))
        self.flush()

    def flush(self) -> None:
        while self._items and self._send(*self._items[0]):
            self._items.pop(0)

    def __len__(self) -> int:
        return len(self._items)
_QUALITY = {"alta": "HighQuality", "media": "NormalQuality", "leve": "LowQuality"}


class QtRecorder(QObject):
    """MP4 H.264/AAC a partir de quadros e blocos de áudio entregues por nós."""

    finished = Signal()
    error = Signal(str)

    def __init__(self, path: Path, size: tuple[int, int], fps: int, quality: str):
        super().__init__()
        from PySide6.QtCore import QSize
        from PySide6.QtMultimedia import (
            QAudioBufferInput, QAudioFormat, QMediaCaptureSession, QMediaFormat, QMediaRecorder, QVideoFrameInput,
        )

        self._fmt = QAudioFormat()
        self._fmt.setSampleRate(48000)
        self._fmt.setChannelCount(2)
        self._fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        self._video = QVideoFrameInput()
        self._audio = QAudioBufferInput(self._fmt)
        self._session = QMediaCaptureSession()
        self._session.setVideoFrameInput(self._video)
        self._session.setAudioBufferInput(self._audio)
        self._rec = QMediaRecorder()
        self._session.setRecorder(self._rec)
        mf = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
        mf.setVideoCodec(QMediaFormat.VideoCodec.H264)
        mf.setAudioCodec(QMediaFormat.AudioCodec.AAC)
        self._rec.setMediaFormat(mf)
        self._rec.setEncodingMode(QMediaRecorder.EncodingMode.ConstantQualityEncoding)
        self._rec.setQuality(getattr(QMediaRecorder.Quality, _QUALITY.get(quality, "NormalQuality")))
        self._rec.setVideoResolution(QSize(*size))
        self._rec.setVideoFrameRate(fps)
        self._rec.setAudioSampleRate(48000)
        self._rec.setAudioChannelCount(2)
        self._rec.setAudioBitRate(160_000)
        self._rec.setOutputLocation(QUrl.fromLocalFile(str(path)))
        self._rec.errorOccurred.connect(lambda _e, msg: self.error.emit(msg or "erro na gravação"))
        self._rec.recorderStateChanged.connect(self._on_state)
        self._stopping = False
        self.dropped = 0
        self._queue = AudioQueue(self._send_audio_now)
        self._audio.readyToSendAudioBuffer.connect(self._queue.flush)

    def _on_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaRecorder

        if self._stopping and state == QMediaRecorder.RecorderState.StoppedState:
            self._stopping = False
            self.finished.emit()

    def start(self) -> None:
        self._rec.record()

    def stop(self) -> None:
        from PySide6.QtMultimedia import QMediaRecorder

        self._stopping = True
        if self._rec.recorderState() == QMediaRecorder.RecorderState.StoppedState:
            self._stopping = False
            self.finished.emit()
            return
        self._rec.stop()

    def send_video(self, frame) -> None:
        if not self._video.sendVideoFrame(frame):
            self.dropped += 1

    def _send_audio_now(self, data: bytes, us: int) -> bool:
        from PySide6.QtMultimedia import QAudioBuffer

        return bool(self._audio.sendAudioBuffer(QAudioBuffer(data, self._fmt, us)))

    def send_audio(self, data: bytes, us: int) -> None:
        self._queue.push(data, us)


def _default_audio(mic_id, system_audio):
    from .audio import AudioCapture

    return AudioCapture(mic_id, system_audio)


def _default_pump(screen, crop, out_size, fps):
    from .video import FramePump

    return FramePump(screen, crop, out_size, fps)


def _default_mic_resolver(saved: str):
    from .audio import resolve_microphone

    return resolve_microphone(saved)


class RecordingSession(QObject):
    state_changed = Signal(str)
    countdown_tick = Signal(int)  # segundos restantes
    saved = Signal(object, int)  # Path final, tamanho
    compressing = Signal(object)  # Path final pretendido
    failed = Signal(str)
    warning = Signal(str)

    def __init__(
        self, settings: Settings, monitor: Monitor, area: QRect, screen, *,
        now: Callable[[], datetime] = datetime.now,
        recorder_factory=None, audio_factory=None, pump_factory=None,
        finalize_fn=None, time_fn: Callable[[], float] = time.perf_counter,
        mic_resolver=None, sync_finalize: bool = False, stop_timeout_ms: int = STOP_TIMEOUT_MS, parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.monitor = monitor
        self.area = QRect(area)
        self.screen = screen
        self._now = now
        self._recorder_factory = recorder_factory or QtRecorder
        self._audio_factory = audio_factory or _default_audio
        self._pump_factory = pump_factory or _default_pump
        self._finalize_fn = finalize_fn
        self._mic_resolver = mic_resolver or _default_mic_resolver
        self._sync_finalize = sync_finalize
        self.clock = RecordingClock(time_fn=time_fn)
        self.state = "idle"
        self.recorder = self.audio = self.pump = None
        self.final: Path | None = None
        self.temp: Path | None = None
        self._countdown_left = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_step)
        self._worker = None
        self._finalized = False
        self._compress_on_finish = settings.rec_compress
        self._stop_watchdog = QTimer(self)
        self._stop_watchdog.setSingleShot(True)
        self._stop_watchdog.setInterval(stop_timeout_ms)
        self._stop_watchdog.timeout.connect(self._on_recorder_finished)

    # ------------------------------------------------------------ estado
    def _set(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)

    def elapsed_ms(self) -> int:
        return self.clock.now_us() // 1000

    # ------------------------------------------------------------ início
    def begin(self, countdown: bool) -> None:
        if countdown:
            self._countdown_left = COUNTDOWN_SECONDS
            self._set("countdown")
            self.countdown_tick.emit(self._countdown_left)
            self._countdown_timer.start()
        else:
            self._start_recording()

    def _countdown_step(self) -> None:
        self._countdown_left -= 1
        if self._countdown_left > 0:
            self.countdown_tick.emit(self._countdown_left)
            return
        self._countdown_timer.stop()
        self._start_recording()

    def _start_recording(self) -> None:
        try:
            self._start_recording_inner()
        except Exception as e:  # noqa: BLE001
            self._finalized = True  # nada a salvar: o gravador não chegou a começar
            self._stop_inputs()
            if self.recorder is not None:
                try:
                    self.recorder.stop()
                except Exception:  # noqa: BLE001
                    pass
            self._delete_temp()
            self._set("done")
            self.failed.emit(f"Não foi possível começar a gravação: {e}")

    def _start_recording_inner(self) -> None:
        s = self.settings
        crop = crop_box(self.monitor, self.area)
        out = output_size(crop[2], crop[3], s.rec_resolution)
        if out == (crop[2] // 2 * 2, crop[3] // 2 * 2):
            # sem redução: corta o pixel ímpar em vez de redimensionar cada quadro
            crop = (crop[0], crop[1], out[0], out[1])
        folder = Path(s.video_dir)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._set("done")
            self.failed.emit(f"Não foi possível usar a pasta dos vídeos: {e}")
            return
        self.final = folder / video_filename(self._now())
        self.temp = temp_path(self.final)
        mic_id = None if s.mic_mode == "off" else self._mic_resolver(s.mic_device)
        if s.mic_mode != "off" and mic_id is None:
            self.warning.emit("Nenhum microfone encontrado")
        self.recorder = self._recorder_factory(self.temp, out, s.rec_fps, s.rec_quality)
        self.audio = self._audio_factory(mic_id, s.system_audio)
        self.pump = self._pump_factory(self.screen, crop, out, s.rec_fps)
        if s.mic_mode == "ptt":
            self.audio.set_mic_open(False)
        self.recorder.error.connect(self._on_recorder_error)
        self.recorder.finished.connect(self._on_recorder_finished)
        self.pump.frame_ready.connect(self.recorder.send_video)
        self.audio.block_ready.connect(self.recorder.send_audio)
        self.audio.warning.connect(self.warning.emit)
        if hasattr(self.pump, "warning"):
            self.pump.warning.connect(self.warning.emit)
        self.recorder.start()
        self.clock.start()
        self.pump.start(self.clock)
        self.audio.start(self.clock)
        self._set("recording")

    # ------------------------------------------------------------ controle
    def pause(self) -> None:
        if self.state == "recording":
            self.clock.pause()
            self._set("paused")

    def resume(self) -> None:
        if self.state == "paused":
            self.clock.resume()
            self._set("recording")

    def _stop_inputs(self) -> None:
        if self.pump is not None:
            self.pump.stop()
        if self.audio is not None:
            self.audio.stop()

    def stop(self) -> None:
        if self.state == "countdown":
            self.cancel()
            return
        if self.state not in ("recording", "paused"):
            return
        self.clock.resume()
        self._stop_inputs()
        self._set("stopping")
        self._stop_watchdog.start()
        self.recorder.stop()

    def cancel(self) -> None:
        self._countdown_timer.stop()
        was_recording = self.state in ("recording", "paused")
        self._set("cancelled")
        if was_recording:
            self._stop_inputs()
            try:
                self.recorder.finished.disconnect(self._on_recorder_finished)
            except (RuntimeError, TypeError):
                pass
            self.recorder.finished.connect(self._delete_temp)
            self.recorder.stop()

    def _delete_temp(self) -> None:
        if self.temp is not None:
            self.temp.unlink(missing_ok=True)

    # ------------------------------------------------------------ fim
    def _finalize(self, compress: bool) -> None:
        if self.temp is None or not self.temp.exists() or self.temp.stat().st_size == 0:
            self.failed.emit("A gravação não gerou nenhum arquivo")
            return
        quality = self.settings.rec_quality
        if self._sync_finalize:
            fn = self._finalize_fn
            if fn is None:
                from .compress import finalize as fn
            out = fn(self.temp, self.final, compress, quality)
            self.saved.emit(out, out.stat().st_size)
            return
        from .compress import CompressWorker

        worker = CompressWorker(self.temp, self.final, compress, quality)
        worker.done.connect(lambda p, n: self.saved.emit(p, n))
        worker.failed.connect(self.failed.emit)
        if compress:
            self.compressing.emit(self.final)
        self._worker = worker
        worker.start()

    def _on_recorder_finished(self) -> None:
        self._stop_watchdog.stop()
        if self.state == "cancelled" or self._finalized:
            return
        self._finalized = True
        self._set("done")
        self._finalize(self._compress_on_finish)

    def _on_recorder_error(self, message: str) -> None:
        if self.state in ("done", "cancelled", "stopping"):
            return
        # para tudo e espera o gravador fechar o arquivo antes de salvar o que foi gravado
        self._stop_inputs()
        self._compress_on_finish = False
        self._set("stopping")
        self.failed.emit(f"A gravação parou: {message}")
        self._stop_watchdog.start()
        self.recorder.stop()
