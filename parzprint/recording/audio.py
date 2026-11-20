"""Captura do microfone (Qt) e do som do computador (loopback WASAPI), misturados em blocos."""

from __future__ import annotations

import threading
from collections.abc import Callable
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from .audio_mix import BLOCK_FRAMES, CHANNELS, SAMPLE_RATE, Resampler, mix_block
from .clock import RecordingClock

MAX_BACKLOG = SAMPLE_RATE  # no máximo 1 s guardado por fonte; o excesso é descartado
MIC_FAIL_READS = 25  # ~0,5 s com erro e sem som até considerar que o microfone caiu
# Atraso acumulado só é cortado quando passa de 300 ms (desvio lento do relógio do aparelho).
# Abaixo disso é a oscilação normal da leitura, que com o PC ocupado chega a dezenas de ms:
# cortar ali picota o áudio.
CUSHION = SAMPLE_RATE * 100 // 1000
CUSHION_MAX = SAMPLE_RATE * 300 // 1000


# ---------------------------------------------------------------- dispositivos
def _qt_devices() -> list:
    from PySide6.QtMultimedia import QMediaDevices

    default = QMediaDevices.defaultAudioInput()
    default_id = bytes(default.id()).decode("utf-8", "replace") if not default.isNull() else ""
    out = []
    for d in QMediaDevices.audioInputs():
        dev_id = bytes(d.id()).decode("utf-8", "replace")
        out.append(SimpleNamespace(id=dev_id, name=d.description(), default=dev_id == default_id))
    return out


def list_microphones(devices: list | None = None) -> list[tuple[str, str]]:
    devices = _qt_devices() if devices is None else devices
    return [(d.id, d.name) for d in devices]


def resolve_microphone(saved_id: str, devices: list | None = None) -> str | None:
    devices = _qt_devices() if devices is None else devices
    if not devices:
        return None
    if saved_id and any(d.id == saved_id for d in devices):
        return saved_id
    default = next((d for d in devices if d.default), devices[0])
    return default.id


def is_fatal_audio_error(error) -> bool:
    """Falta de dados (Underrun) é normal numa leitura rápida; só os demais erros contam."""
    from PySide6.QtMultimedia import QAudio

    return error not in (QAudio.Error.NoError, QAudio.Error.UnderrunError)


# ---------------------------------------------------------------- fontes
class _Fifo:
    def __init__(self):
        self._lock = threading.Lock()
        self._parts: list[np.ndarray] = []
        self._size = 0

    def push(self, data: np.ndarray) -> None:
        with self._lock:
            self._parts.append(data)
            self._size += len(data)
            while self._size > MAX_BACKLOG and len(self._parts) > 1:
                self._size -= len(self._parts.pop(0))

    def take(self) -> np.ndarray:
        with self._lock:
            parts, self._parts, self._size = self._parts, [], 0
        return np.concatenate(parts) if parts else np.zeros((0, CHANNELS), np.float32)


class MicSource:
    """Microfone pelo Qt (QAudioSource), convertido para 48 kHz estéreo float."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.on_error: Callable[[str], None] | None = None
        self._fifo = _Fifo()
        self._source = None
        self._io = None
        self._fmt = None
        self._failed = False
        self._bad_reads = 0

    def start(self) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

        device = next(
            (d for d in QMediaDevices.audioInputs() if bytes(d.id()).decode("utf-8", "replace") == self.device_id),
            None,
        )
        if device is None:
            self._fail("Microfone não encontrado")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(SAMPLE_RATE)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        self._fmt = fmt
        self._source = QAudioSource(device, fmt)
        self._io = self._source.start()
        if self._io is None:
            self._source = None
            self._fail("Não foi possível abrir o microfone (confira a permissão de microfone do Windows)")
            return
        self._resampler = Resampler(fmt.sampleRate(), max(1, fmt.channelCount()))
        self._io.readyRead.connect(self._read_io)

    def _check_error(self, got_audio: bool) -> None:
        # o sinal stateChanged não chega ao Python nesta versão do PySide; confere a cada leitura.
        # Logo ao abrir o Qt pode marcar um erro que some sozinho: só conta se persistir sem som.
        if self._source is None or self._failed:
            return
        if got_audio or not is_fatal_audio_error(self._source.error()):
            self._bad_reads = 0
            return
        self._bad_reads += 1
        if self._bad_reads >= MIC_FAIL_READS:
            self._failed = True
            self._fail("O microfone parou de responder")

    def _fail(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)

    def _read_io(self) -> None:
        from PySide6.QtMultimedia import QAudioFormat

        if self._io is None:
            return
        raw = bytes(self._io.readAll())
        if not raw:
            return
        sf = self._fmt.sampleFormat()
        dtype = {
            QAudioFormat.SampleFormat.Float: np.float32,
            QAudioFormat.SampleFormat.Int16: np.int16,
            QAudioFormat.SampleFormat.Int32: np.int32,
            QAudioFormat.SampleFormat.UInt8: np.uint8,
        }.get(sf, np.float32)
        data = np.frombuffer(raw[: len(raw) - len(raw) % np.dtype(dtype).itemsize], dtype)
        if dtype is np.int16:
            data = data.astype(np.float32) / 32768
        elif dtype is np.int32:
            data = data.astype(np.float32) / 2147483648
        elif dtype is np.uint8:
            data = (data.astype(np.float32) - 128) / 128
        ch = max(1, self._fmt.channelCount())
        data = data[: len(data) - len(data) % ch]
        self._fifo.push(self._resampler.feed(data))

    def read(self) -> np.ndarray:
        self._read_io()
        data = self._fifo.take()
        self._check_error(len(data) > 0)
        return data

    def stop(self) -> None:
        if self._source is not None:
            self._source.stop()
        self._source = self._io = None


class LoopbackSource:
    """Som do computador: loopback WASAPI do dispositivo de saída padrão (PyAudioWPatch)."""

    def __init__(self):
        self.on_error: Callable[[str], None] | None = None
        self._fifo = _Fifo()
        self._pa = None
        self._stream = None
        self._lost = False

    def start(self) -> None:
        try:
            import pyaudiowpatch as pa

            self._pa = pa.PyAudio()
            dev = self._pa.get_default_wasapi_loopback()
            rate, ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxInputChannels"]))
            resampler = Resampler(rate, ch)

            def cb(data, frames, info, status):
                block = np.frombuffer(data, np.float32)
                self._fifo.push(resampler.feed(block[: len(block) - len(block) % ch]))
                return (None, pa.paContinue)

            self._stream = self._pa.open(
                format=pa.paFloat32, channels=ch, rate=rate, input=True,
                input_device_index=dev["index"], frames_per_buffer=max(1, rate // 50), stream_callback=cb,
            )
            self._stream.start_stream()
        except Exception as e:  # noqa: BLE001
            self.stop()
            if self.on_error is not None:
                self.on_error(f"Som do computador indisponível: {e}")

    def read(self) -> np.ndarray:
        if self._stream is not None and not self._lost:
            try:
                alive = self._stream.is_active()
            except Exception:  # noqa: BLE001
                alive = False
            if not alive:
                self._lost = True
                if self.on_error is not None:
                    self.on_error("O som do computador parou de ser capturado (a saída de áudio mudou?)")
        return self._fifo.take()

    def stop(self) -> None:
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa is not None:
                self._pa.terminate()
        except Exception:  # noqa: BLE001
            pass
        self._stream = self._pa = None


# ---------------------------------------------------------------- captura
class AudioCapture(QObject):
    """Junta microfone e som do computador e emite blocos de 20 ms com o carimbo do relógio."""

    block_ready = Signal(bytes, int)  # PCM float32 intercalado, carimbo em µs
    warning = Signal(str)

    def __init__(
        self, mic_id: str | None, system_audio: bool,
        mic_factory: Callable[[str], object] | None = None,
        loopback_factory: Callable[[], object] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mic_id = mic_id
        self._system_audio = system_audio
        self._mic_factory = mic_factory or MicSource
        self._loopback_factory = loopback_factory or LoopbackSource
        self._mic = None
        self._loop = None
        self._mic_open = True
        self._mic_buf = np.zeros((0, CHANNELS), np.float32)
        self._sys_buf = np.zeros((0, CHANNELS), np.float32)
        self._pos = 0  # amostras já emitidas
        self.clock: RecordingClock | None = None
        self._timer: QTimer | None = None

    @property
    def mic_id(self) -> str | None:
        return self._mic_id if self._mic is not None else None

    # -- fontes
    def _open_mic(self) -> None:
        if self._mic_id:
            self._mic = self._mic_factory(self._mic_id)
            self._mic.on_error = self.warning.emit
            self._mic.start()

    def _open_loopback(self) -> None:
        self._loop = self._loopback_factory()
        self._loop.on_error = self.warning.emit
        self._loop.start()

    def start(self, clock: RecordingClock, timer: bool = True) -> None:
        self.clock = clock
        self._open_mic()
        if self._system_audio:
            self._open_loopback()
        if timer:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.tick)
            self._timer.start(20)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self.tick()
        for src in (self._mic, self._loop):
            if src is not None:
                src.stop()
        self._mic = self._loop = None

    def set_mic(self, mic_id: str | None) -> None:
        if self._mic is not None:
            self._mic.stop()
        self._mic = None
        self._mic_buf = np.zeros((0, CHANNELS), np.float32)
        self._mic_id = mic_id
        if self.clock is not None:
            self._open_mic()

    def set_mic_open(self, open_: bool) -> None:
        self._mic_open = open_

    def set_system_audio(self, on: bool) -> None:
        self._system_audio = on
        if on and self._loop is None and self.clock is not None:
            self._open_loopback()
        elif not on and self._loop is not None:
            self._loop.stop()
            self._loop = None
            self._sys_buf = np.zeros((0, CHANNELS), np.float32)

    @staticmethod
    def _cushioned(buf: np.ndarray) -> np.ndarray:
        # se o dispositivo anda mais rápido que o relógio, o atraso cresce; corta de volta
        return buf[-CUSHION:] if len(buf) > CUSHION_MAX else buf

    # -- ritmo
    def tick(self) -> None:
        if self.clock is None:
            return
        mic = self._mic.read() if self._mic is not None else None
        sys_ = self._loop.read() if self._loop is not None else None
        if self.clock.paused:
            return  # o que chegou durante a pausa é descartado
        if mic is not None and len(mic):
            self._mic_buf = self._cushioned(np.concatenate([self._mic_buf, mic]))
        if sys_ is not None and len(sys_):
            self._sys_buf = self._cushioned(np.concatenate([self._sys_buf, sys_]))
        target = self.clock.now_us() * SAMPLE_RATE // 1_000_000
        while self._pos + BLOCK_FRAMES <= target:
            m, self._mic_buf = self._mic_buf[:BLOCK_FRAMES], self._mic_buf[BLOCK_FRAMES:]
            s, self._sys_buf = self._sys_buf[:BLOCK_FRAMES], self._sys_buf[BLOCK_FRAMES:]
            block = mix_block(m if self._mic is not None else None, s, self._mic_open)
            self.block_ready.emit(block.tobytes(), self._pos * 1_000_000 // SAMPLE_RATE)
            self._pos += BLOCK_FRAMES
