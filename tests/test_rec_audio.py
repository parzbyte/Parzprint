import numpy as np

from parzprint.recording.audio_mix import BLOCK_FRAMES, mix_block, to_stereo_48k
from parzprint.recording.clock import RecordingClock


def test_mixer_sums_and_limits():
    a = np.full((960, 2), 0.6, np.float32)
    out = mix_block(a, a, mic_open=True)
    assert out.shape == (960, 2) and out.dtype == np.float32 and out.max() <= 1.0 and out.max() > 0.9


def test_mixer_quiet_signal_passes_unchanged():
    a = np.full((960, 2), 0.3, np.float32)
    assert np.allclose(mix_block(a, None, mic_open=True), 0.3)


def test_mixer_closed_mic_is_silent():
    a = np.full((960, 2), 0.5, np.float32)
    assert np.all(mix_block(a, None, mic_open=False) == 0)


def test_mixer_missing_mic_block_is_silence():
    s = np.full((960, 2), 0.2, np.float32)
    assert np.allclose(mix_block(None, s, mic_open=True), 0.2)


def test_mixer_pads_short_blocks():
    out = mix_block(np.ones((100, 2), np.float32) * 0.1, None, mic_open=True)
    assert out.shape == (BLOCK_FRAMES, 2) and out[500, 0] == 0


def test_to_stereo_48k():
    mono = np.ones(441, np.float32)
    out = to_stereo_48k(mono, 44100, 1)
    assert out.shape == (480, 2)
    st = np.ones((480, 2), np.float32)
    assert to_stereo_48k(st, 48000, 2).shape == (480, 2)


def test_clock_skips_paused_time():
    t = [0.0]
    c = RecordingClock(time_fn=lambda: t[0])
    c.start()
    t[0] = 2.0
    c.pause()
    t[0] = 5.0
    c.resume()
    t[0] = 6.0
    assert c.now_us() == 3_000_000


def test_clock_while_paused_is_frozen():
    t = [0.0]
    c = RecordingClock(time_fn=lambda: t[0])
    c.start()
    t[0] = 1.0
    c.pause()
    t[0] = 9.0
    assert c.now_us() == 1_000_000 and c.paused
