from types import SimpleNamespace

import numpy as np

from parzprint.recording.audio import AudioCapture, list_microphones, resolve_microphone
from parzprint.recording.audio_mix import BLOCK_FRAMES
from parzprint.recording.clock import RecordingClock

DEVS = [SimpleNamespace(id="a", name="Mic A", default=False), SimpleNamespace(id="b", name="Mic B", default=True)]


def test_list_microphones_from_devices():
    assert list_microphones(DEVS) == [("a", "Mic A"), ("b", "Mic B")]


def test_resolve_microphone():
    assert resolve_microphone("a", DEVS) == "a"
    assert resolve_microphone("sumiu", DEVS) == "b"
    assert resolve_microphone("", DEVS) == "b"
    assert resolve_microphone("a", []) is None


class FakeSource:
    def __init__(self, value):
        self.value = value
        self.pending = 0
        self.started = self.stopped = False
        self.on_error = None

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def read(self):
        n, self.pending = self.pending, 0
        return np.full((n, 2), self.value, np.float32)


def _capture(qapp, t, mic=None, sys_=None, system_audio=True):
    mic = mic or FakeSource(0.25)
    sys_ = sys_ or FakeSource(0.25)
    cap = AudioCapture("a", system_audio, mic_factory=lambda dev_id: mic, loopback_factory=lambda: sys_)
    blocks = []
    cap.block_ready.connect(lambda data, us: blocks.append((np.frombuffer(data, np.float32).reshape(-1, 2), us)))
    clock = RecordingClock(time_fn=lambda: t[0])
    clock.start()
    cap.start(clock, timer=False)
    return cap, mic, sys_, blocks


def test_capture_emits_20ms_blocks_with_rising_stamps(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t)
    t[0] = 0.1
    mic.pending = sys_.pending = 4800
    cap.tick()
    assert len(blocks) == 5
    assert [us for _, us in blocks] == [0, 20000, 40000, 60000, 80000]
    assert all(b.shape == (BLOCK_FRAMES, 2) for b, _ in blocks)
    assert np.allclose(blocks[0][0], 0.5)
    cap.stop()
    assert mic.stopped and sys_.stopped


def test_capture_fills_silence_when_sources_are_empty(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t)
    t[0] = 0.04
    cap.tick()
    assert len(blocks) == 2 and np.all(blocks[0][0] == 0)


def test_mic_closed_and_system_off(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t, system_audio=False)
    cap.set_mic_open(False)
    t[0] = 0.02
    mic.pending = 960
    cap.tick()
    assert np.all(blocks[0][0] == 0) and not sys_.started


def test_paused_clock_discards_input(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t)
    clock = cap.clock
    t[0] = 0.02
    cap.tick()
    clock.pause()
    t[0] = 1.0
    mic.pending = 48000
    cap.tick()
    clock.resume()
    t[0] = 1.02
    mic.pending = 960
    cap.tick()
    assert len(blocks) == 2 and np.allclose(blocks[1][0][:, 0], 0.25)


def test_mic_error_warns_and_continues(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t)
    warnings = []
    cap.warning.connect(warnings.append)
    mic.on_error("Microfone desconectado")
    t[0] = 0.02
    cap.tick()
    assert warnings and len(blocks) == 1


def test_set_mic_switches_source(qapp):
    t = [0.0]
    cap, mic, sys_, blocks = _capture(qapp, t)
    new = FakeSource(0.1)
    cap._mic_factory = lambda dev_id: new
    cap.set_mic("b")
    assert mic.stopped and new.started


def test_only_real_errors_count_as_mic_failure():
    from PySide6.QtMultimedia import QAudio

    from parzprint.recording.audio import is_fatal_audio_error

    assert not is_fatal_audio_error(QAudio.Error.NoError)
    assert not is_fatal_audio_error(QAudio.Error.UnderrunError)
    assert is_fatal_audio_error(QAudio.Error.IOError)
    assert is_fatal_audio_error(QAudio.Error.FatalError)
    assert is_fatal_audio_error(QAudio.Error.OpenError)
