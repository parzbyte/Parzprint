"""Testes dos achados da revisão final da gravação."""

import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QCoreApplication, QElapsedTimer, QObject, QRect, Signal

from parzprint.capture import Monitor
from parzprint.recording.audio_mix import Resampler
from parzprint.recording.compress import CompressWorker
from parzprint.recording.session import RecordingSession
from parzprint.settings import Settings

from tests.test_app_recording import FakeHotkey, FakeTray, FakeWin
from tests.test_rec_bar import FakeLayer
from tests.test_rec_session import FakeAudio, FakePump, FakeRecorder


def pump_events(ms=300, until=lambda: False):
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < ms and not until():
        QCoreApplication.processEvents()
        time.sleep(0.005)


# ---------------------------------------------------------------- sessão
class SilentRecorder(FakeRecorder):
    """Recorder que nunca avisa que terminou."""

    def stop(self):
        self.stopped = True


class BrokenRecorder(FakeRecorder):
    def start(self):
        raise RuntimeError("codificador indisponível")


def session(tmp_path, recorder_cls=FakeRecorder, area=QRect(100, 100, 801, 601), **settings):
    s = Settings(video_dir=str(tmp_path), **settings)
    mon = Monitor(1, 0, 0, 1920, 1080, Image.new("RGB", (4, 4)), dpr=1.0)
    made = {}

    def rec(path, size, fps, quality):
        made["rec"] = recorder_cls(path, size, fps, quality)
        return made["rec"]

    def audio(mic_id, sys_):
        made["audio"] = FakeAudio(mic_id, sys_)
        return made["audio"]

    def pump(screen, crop, out, fps):
        made["pump"] = FakePump(screen, crop, out, fps)
        made["pump"].stopped = False
        made["pump"].stop = lambda: setattr(made["pump"], "stopped", True)
        return made["pump"]

    def finalize(temp, final, compress, quality):
        temp.replace(final)
        return final

    sess = RecordingSession(s, mon, area, None, now=lambda: datetime(2026, 11, 20, 10, 0, 0),
                            recorder_factory=rec, audio_factory=audio, pump_factory=pump,
                            finalize_fn=finalize, mic_resolver=lambda saved: "mic1", sync_finalize=True,
                            stop_timeout_ms=150)
    return sess, made


def test_stop_watchdog_finalizes_when_recorder_never_finishes(tmp_path, qapp):
    sess, made = session(tmp_path, SilentRecorder)
    saved = []
    sess.saved.connect(lambda p, n: saved.append(p))
    sess.begin(False)
    sess.stop()
    pump_events(1000, until=lambda: saved)
    assert saved and saved[0].name == "Parzprint_2026-11-20_10-00-00.mp4" and sess.state == "done"


def test_recorder_error_stops_recorder_before_finalizing(tmp_path, qapp):
    sess, made = session(tmp_path)
    order = []
    rec = None
    sess.begin(False)
    rec = made["rec"]
    orig_stop = rec.stop
    rec.stop = lambda: (order.append("stop"), orig_stop())
    sess.saved.connect(lambda p, n: order.append("saved"))
    rec.error.emit("disco cheio")
    pump_events(500, until=lambda: "saved" in order)
    assert order[:2] == ["stop", "saved"]


def test_start_failure_tears_down_and_reports(tmp_path, qapp):
    sess, made = session(tmp_path, BrokenRecorder)
    errors = []
    sess.failed.connect(errors.append)
    sess.begin(False)
    assert sess.state == "done" and errors and "codificador indisponível" in errors[0]
    assert made["pump"].stopped and made["audio"].stopped


def test_odd_area_at_original_is_trimmed_not_scaled(tmp_path, qapp):
    sess, made = session(tmp_path)
    sess.begin(False)
    assert made["pump"].crop == (100, 100, 800, 600) and made["pump"].out_size == (800, 600)


def test_pump_warning_reaches_session(tmp_path, qapp):
    sess, made = session(tmp_path)
    warnings = []
    sess.warning.connect(warnings.append)
    sess.begin(False)
    made["pump"].warning.emit("A captura da tela parou")
    assert warnings == ["A captura da tela parou"]


# ---------------------------------------------------------------- recorder e áudio
def test_refused_audio_blocks_are_retried_in_order(qapp):
    from parzprint.recording.session import AudioQueue

    sent, accept = [], [False]

    def send(data, us):
        if accept[0]:
            sent.append(us)
        return accept[0]

    q = AudioQueue(send)
    q.push(b"a", 0)
    q.push(b"b", 20000)
    assert sent == [] and len(q) == 2
    accept[0] = True
    q.push(b"c", 40000)
    assert sent == [0, 20000, 40000] and len(q) == 0


def test_resampler_is_continuous_across_chunks():
    t = np.arange(44100) / 44100
    wave = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    r = Resampler(44100, 1)
    out = np.concatenate([r.feed(wave[i:i + 441]) for i in range(0, 44100, 441)])
    assert abs(len(out) - 48000) <= 2
    jumps = np.abs(np.diff(out[:, 0]))
    assert jumps.max() < 0.08  # um seno de 440 Hz em 48 kHz varia no máximo ~0,058 por amostra


def test_capture_trims_backlog_to_cushion(qapp):
    from parzprint.recording.audio import AudioCapture
    from parzprint.recording.clock import RecordingClock

    from tests.test_rec_audio_devices import FakeSource

    t = [0.0]
    mic, sys_ = FakeSource(0.1), FakeSource(0.1)
    cap = AudioCapture("a", True, mic_factory=lambda d: mic, loopback_factory=lambda: sys_)
    clock = RecordingClock(time_fn=lambda: t[0])
    clock.start()
    cap.start(clock, timer=False)
    t[0] = 0.02
    sys_.pending = 48000  # 1 s de atraso acumulado
    cap.tick()
    assert len(cap._sys_buf) <= 48000 * 0.06


def test_loopback_failure_mid_recording_warns_once(qapp):
    from parzprint.recording.audio import LoopbackSource

    class Stream:
        active = True

        def is_active(self):
            return self.active

    src = LoopbackSource()
    src._stream = Stream()
    warnings = []
    src.on_error = warnings.append
    src.read()
    assert warnings == []
    src._stream.active = False
    src.read()
    src.read()
    assert len(warnings) == 1 and "som do computador" in warnings[0].lower()


def test_pump_reports_capture_error(qapp):
    from parzprint.recording.video import FramePump

    pump = FramePump(None, (0, 0, 10, 10), (10, 10), 30)
    got = []
    pump.warning.connect(got.append)
    pump._on_capture_error(1, "monitor desconectado")
    assert got and "monitor desconectado" in got[0]


# ---------------------------------------------------------------- compressão e saída
def test_abort_compression_keeps_original_under_final_name(tmp_path, qapp):
    temp = tmp_path / "v.gravando.mp4"
    temp.write_bytes(b"o" * 1000)
    release = threading.Event()

    class Proc:
        def __init__(self):
            self.killed = False

        def kill(self):
            self.killed = True
            release.set()

    proc = Proc()

    def runner(args, register=None):
        register(proc)
        release.wait(5)
        return 1 if proc.killed else 0

    w = CompressWorker(temp, tmp_path / "v.mp4", True, "media", runner=runner)
    w.start()
    time.sleep(0.1)
    w.abort(timeout=3)
    assert proc.killed and (tmp_path / "v.mp4").read_bytes() == b"o" * 1000
    assert not list(tmp_path.glob("*.comprimindo.mp4")) and not temp.exists()


# ---------------------------------------------------------------- controlador e barrinha
def test_shutdown_waits_for_session_still_stopping(qapp):
    from parzprint.recording.controller import RecordingController
    from tests.test_app_recording import FakeSession

    class SlowStop(FakeSession):
        def stop(self):
            self.stopped = True
            self.state = "stopping"
            self.state_changed.emit("stopping")

            def later():
                self.state = "done"
                self.state_changed.emit("done")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, later)

    made = {}

    def factory(*a, **k):
        made["s"] = SlowStop()
        return made["s"]

    c = RecordingController(Settings(), FakeTray(), lambda s: None, session_factory=factory,
                            layer_factory=FakeWin, frame_factory=FakeWin,
                            bar_factory=lambda s, st, l: FakeWin(), hotkey_factory=FakeHotkey,
                            key_down=lambda h: False, opener=lambda p: None, screen_for=lambda a: None)
    c.start(Monitor(1, 0, 0, 10, 10, Image.new("RGB", (2, 2))), QRect(0, 0, 10, 10), [])
    c.stop()
    assert made["s"].state == "stopping"
    c.shutdown(timeout_ms=2000)
    assert made["s"].state == "done"


def test_bar_raised_when_draw_mode_turns_on(qapp):
    from parzprint.recording.controller import RecordingController
    from tests.test_app_recording import FakeSession

    class Bar(FakeWin):
        raised = 0

        def raise_(self):
            Bar.raised += 1

    class LayerWin(FakeWin):
        def set_draw_mode(self, on):
            self.draw_mode = on
            self.draw_mode_changed.emit(on)

    layer = LayerWin()
    c = RecordingController(Settings(), FakeTray(), lambda s: None, session_factory=lambda *a, **k: FakeSession(),
                            layer_factory=lambda *a: layer, frame_factory=FakeWin,
                            bar_factory=lambda s, st, l: Bar(), hotkey_factory=FakeHotkey,
                            key_down=lambda h: False, opener=lambda p: None, screen_for=lambda a: None)
    c.start(Monitor(1, 0, 0, 10, 10, Image.new("RGB", (2, 2))), QRect(0, 0, 10, 10), [])
    before = Bar.raised
    layer.set_draw_mode(True)
    assert Bar.raised > before


def test_bar_settings_saved_onto_current_settings(qapp):
    from parzprint.recording.controller import RecordingController
    from tests.test_app_recording import FakeSession

    saved = []
    bar = FakeWin()
    c = RecordingController(Settings(), FakeTray(), saved.append, session_factory=lambda *a, **k: FakeSession(),
                            layer_factory=FakeWin, frame_factory=FakeWin, bar_factory=lambda s, st, l: bar,
                            hotkey_factory=FakeHotkey, key_down=lambda h: False, opener=lambda p: None,
                            screen_for=lambda a: None)
    c.start(Monitor(1, 0, 0, 10, 10, Image.new("RGB", (2, 2))), QRect(0, 0, 10, 10), [])
    old = c.settings
    c.settings = Settings(image_format="JPG")  # salvo em Configurações durante a gravação
    old.mic_device, old.mic_mode, old.system_audio = "m2", "ptt", False
    bar.settings_changed.emit(old)
    s = saved[-1]
    assert s.image_format == "JPG" and (s.mic_device, s.mic_mode, s.system_audio) == ("m2", "ptt", False)


class BarAudio:
    def __init__(self, mic=None):
        self.calls = []
        self.mic_id = mic

    def set_mic(self, mic_id):
        self.calls.append(("mic", mic_id))
        self.mic_id = mic_id

    def set_mic_open(self, v):
        self.calls.append(("open", v))

    def set_system_audio(self, v):
        self.calls.append(("sys", v))


class BarSession(QObject):
    state_changed = Signal(str)
    warning = Signal(str)

    def __init__(self, audio):
        super().__init__()
        self.audio, self.state = audio, "recording"

    def stop(self):
        pass

    def elapsed_ms(self):
        return 0


def test_bar_shows_resolved_default_mic(qapp):
    from parzprint.recording.recordbar import RecordBar

    bar = RecordBar(BarSession(BarAudio()), Settings(mic_device=""), FakeLayer(),
                    mics=[("m1", "Um"), ("m2", "Dois")], resolve=lambda saved: "m2")
    assert bar.mic_combo.currentData() == "m2"


def test_bar_choosing_no_mic_turns_mode_off(qapp):
    from parzprint.recording.recordbar import RecordBar

    audio = BarAudio("m1")
    s = Settings(mic_device="m1")
    bar = RecordBar(BarSession(audio), s, FakeLayer(), mics=[("m1", "Um")], resolve=lambda saved: saved or "m1")
    bar.mic_combo.setCurrentIndex(bar.mic_combo.findData(""))
    assert s.mic_mode == "off" and bar.mode_combo.currentData() == "off" and ("mic", None) in audio.calls


def test_bar_mode_from_off_opens_the_microphone(qapp):
    from parzprint.recording.recordbar import RecordBar

    audio = BarAudio(None)
    s = Settings(mic_device="m1", mic_mode="off")
    bar = RecordBar(BarSession(audio), s, FakeLayer(), mics=[("m1", "Um")], resolve=lambda saved: saved or "m1")
    bar.mode_combo.setCurrentIndex(bar.mode_combo.findData("always"))
    assert ("mic", "m1") in audio.calls and audio.calls[-1] == ("open", True)


def test_bar_device_change_while_off_keeps_mic_closed(qapp):
    from parzprint.recording.recordbar import RecordBar

    audio = BarAudio(None)
    s = Settings(mic_device="m1", mic_mode="off")
    bar = RecordBar(BarSession(audio), s, FakeLayer(), mics=[("m1", "Um"), ("m2", "Dois")],
                    resolve=lambda saved: saved or "m1")
    bar.mic_combo.setCurrentIndex(bar.mic_combo.findData("m2"))
    assert ("mic", "m2") not in audio.calls and s.mic_device == "m2"


