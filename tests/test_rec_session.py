from datetime import datetime

from PIL import Image
from PySide6.QtCore import QObject, QRect, Signal

from parzprint.capture import Monitor
from parzprint.recording.session import RecordingSession
from parzprint.settings import Settings


class FakeRecorder(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, path, size, fps, quality):
        super().__init__()
        self.path, self.size, self.fps, self.quality = path, size, fps, quality
        self.frames, self.audio = [], []
        self.started = self.stopped = False

    def start(self):
        self.started = True
        self.path.write_bytes(b"video")

    def stop(self):
        self.stopped = True
        self.finished.emit()

    def send_video(self, frame):
        self.frames.append(frame)

    def send_audio(self, data, us):
        self.audio.append(us)


class FakeAudio(QObject):
    block_ready = Signal(bytes, int)
    warning = Signal(str)

    def __init__(self, mic_id, system_audio):
        super().__init__()
        self.mic_id, self.system_audio = mic_id, system_audio
        self.mic_open = True
        self.started = self.stopped = False

    def start(self, clock):
        self.started = True

    def stop(self):
        self.stopped = True

    def set_mic_open(self, v):
        self.mic_open = v


class FakePump(QObject):
    frame_ready = Signal(object)

    def __init__(self, screen, crop, out_size, fps):
        super().__init__()
        self.crop, self.out_size, self.fps = crop, out_size, fps

    def start(self, clock):
        pass

    def stop(self):
        pass


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(tmp_path, qapp, **settings):
    s = Settings(video_dir=str(tmp_path), **settings)
    mon = Monitor(1, 0, 0, 1920, 1080, Image.new("RGB", (1920, 1080)))
    made = {}
    finalized = []

    def rec(path, size, fps, quality):
        made["rec"] = FakeRecorder(path, size, fps, quality)
        return made["rec"]

    def audio(mic_id, system_audio):
        made["audio"] = FakeAudio(mic_id, system_audio)
        return made["audio"]

    def pump(screen, crop, out_size, fps):
        made["pump"] = FakePump(screen, crop, out_size, fps)
        return made["pump"]

    def finalize(temp, final, compress, quality):
        finalized.append((temp, final, compress, quality))
        temp.replace(final)
        return final

    clock = Clock()
    sess = RecordingSession(
        s, mon, QRect(100, 100, 801, 601), None, now=lambda: datetime(2026, 11, 20, 10, 0, 0),
        recorder_factory=rec, audio_factory=audio, pump_factory=pump, finalize_fn=finalize,
        time_fn=clock, mic_resolver=lambda saved: "mic1", sync_finalize=True,
    )
    return sess, made, finalized, clock


def test_stop_during_countdown_leaves_no_file(tmp_path, qapp):
    sess, made, _, _ = make(tmp_path, qapp)
    states = []
    sess.state_changed.connect(states.append)
    sess.begin(True)
    assert sess.state == "countdown"
    sess.stop()
    assert sess.state == "cancelled" and "rec" not in made and list(tmp_path.iterdir()) == []


def test_begin_without_countdown_wires_everything(tmp_path, qapp):
    sess, made, _, _ = make(tmp_path, qapp, rec_resolution="480", rec_fps=15, rec_quality="leve")
    sess.begin(False)
    assert sess.state == "recording"
    rec = made["rec"]
    assert rec.started and rec.size == (638, 480) and rec.fps == 15 and rec.quality == "leve"
    assert rec.path.name == "Parzprint_2026-11-20_10-00-00.gravando.mp4"
    assert made["pump"].crop == (100, 100, 801, 601) and made["audio"].mic_id == "mic1"
    made["pump"].frame_ready.emit("f")
    made["audio"].block_ready.emit(b"x", 20000)
    assert rec.frames == ["f"] and rec.audio == [20000]


def test_mic_mode_off_and_ptt(tmp_path, qapp):
    sess, made, _, _ = make(tmp_path, qapp, mic_mode="off")
    sess.begin(False)
    assert made["audio"].mic_id is None
    sess2, made2, _, _ = make(tmp_path, qapp, mic_mode="ptt")
    sess2.begin(False)
    assert made2["audio"].mic_open is False


def test_pause_resume_and_elapsed(tmp_path, qapp):
    sess, made, _, clock = make(tmp_path, qapp)
    sess.begin(False)
    clock.t = 2.0
    sess.pause()
    assert sess.state == "paused"
    clock.t = 5.0
    sess.resume()
    clock.t = 6.0
    assert sess.elapsed_ms() == 3000 and sess.state == "recording"


def test_stop_calls_finalize_with_settings(tmp_path, qapp):
    sess, made, finalized, _ = make(tmp_path, qapp, rec_quality="alta", rec_compress=False)
    saved = []
    sess.saved.connect(lambda p, n: saved.append((p.name, n)))
    sess.begin(False)
    sess.stop()
    temp, final, compress, quality = finalized[0]
    assert compress is False and quality == "alta" and final.name == "Parzprint_2026-11-20_10-00-00.mp4"
    assert saved == [("Parzprint_2026-11-20_10-00-00.mp4", 5)] and sess.state == "done"
    assert made["audio"].stopped and made["rec"].stopped


def test_recorder_error_keeps_partial_file(tmp_path, qapp):
    sess, made, finalized, _ = make(tmp_path, qapp, rec_compress=True)
    errors = []
    sess.failed.connect(errors.append)
    sess.begin(False)
    made["rec"].error.emit("disco cheio")
    assert errors and "disco cheio" in errors[0]
    assert finalized and finalized[0][2] is False
    assert (tmp_path / "Parzprint_2026-11-20_10-00-00.mp4").exists()


def test_cancel_while_recording_deletes_temp(tmp_path, qapp):
    sess, made, finalized, _ = make(tmp_path, qapp)
    sess.begin(False)
    sess.cancel()
    assert sess.state == "cancelled" and not finalized and list(tmp_path.iterdir()) == []
