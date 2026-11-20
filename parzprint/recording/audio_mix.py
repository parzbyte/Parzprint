"""Mistura do microfone com o som do computador, em blocos de 20 ms (48 kHz, estéreo, float32)."""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 48000
CHANNELS = 2
BLOCK_FRAMES = 960  # 20 ms
_KNEE = 0.9


def _fit(block: np.ndarray | None) -> np.ndarray:
    out = np.zeros((BLOCK_FRAMES, CHANNELS), np.float32)
    if block is not None and len(block):
        n = min(len(block), BLOCK_FRAMES)
        out[:n] = block[:n]
    return out


def mix_block(mic: np.ndarray | None, system: np.ndarray | None, mic_open: bool) -> np.ndarray:
    """Soma as duas fontes; fonte ausente ou microfone fechado entram como silêncio.

    Acima de 0,9 aplica um limitador suave (tanh) para não estourar.
    """
    out = _fit(system)
    if mic_open:
        out += _fit(mic)
    over = np.abs(out) > _KNEE
    if over.any():
        sign = np.sign(out[over])
        excess = np.abs(out[over]) - _KNEE
        out[over] = sign * (_KNEE + (1 - _KNEE) * np.tanh(excess / (1 - _KNEE)))
    return out


def _to_stereo(samples: np.ndarray, channels: int) -> np.ndarray:
    data = np.asarray(samples, np.float32).reshape(-1, channels)
    if channels == 1:
        return np.repeat(data, 2, axis=1)
    return data[:, :2] if channels > 2 else data


class Resampler:
    """Converte blocos seguidos para 48 kHz estéreo sem emendas entre um bloco e outro."""

    def __init__(self, rate: int, channels: int):
        self.rate = rate
        self.channels = channels
        self._step = rate / SAMPLE_RATE
        self._last: np.ndarray | None = None
        self._t = 0.0  # próxima posição de saída, em amostras de entrada a partir de _last

    def feed(self, samples: np.ndarray) -> np.ndarray:
        data = _to_stereo(samples, self.channels)
        if self.rate == SAMPLE_RATE or len(data) == 0:
            return np.ascontiguousarray(data)
        if self._last is not None:
            data = np.concatenate([self._last[None, :], data])
        end = len(data) - 1
        n = int(np.floor((end - self._t) / self._step)) + 1 if end >= self._t else 0
        pos = self._t + np.arange(n) * self._step
        src = np.arange(len(data))
        out = np.stack([np.interp(pos, src, data[:, c]) for c in range(2)], axis=1).astype(np.float32)
        self._t = (self._t + n * self._step) - end
        self._last = data[-1].copy()
        return out


def to_stereo_48k(samples: np.ndarray, rate: int, channels: int) -> np.ndarray:
    """Converte para 48 kHz estéreo float32 (interpolação linear; mono vira estéreo)."""
    data = np.asarray(samples, np.float32).reshape(-1, channels)
    if channels == 1:
        data = np.repeat(data, 2, axis=1)
    elif channels > 2:
        data = data[:, :2]
    if rate == SAMPLE_RATE or len(data) == 0:
        return np.ascontiguousarray(data)
    n_out = int(round(len(data) * SAMPLE_RATE / rate))
    src = np.arange(len(data))
    pos = np.linspace(0, len(data) - 1, n_out)
    return np.stack([np.interp(pos, src, data[:, c]) for c in range(2)], axis=1).astype(np.float32)
