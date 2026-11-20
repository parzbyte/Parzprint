from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRect, Signal

from parzprint.capture import Monitor
from parzprint.hotkey import is_key_down
from parzprint.recording.controller import RecordingController
from parzprint.settings import Settings


class FakeTray:
    def __init__(self):
        self.messages, self.recording = [], []

    def notify(self, title, text):
        self.messages.append(text)

    def set_recording(self, on):
        self.recording.append(on)


class FakeAudio:
    def __init__(self):
        self.open = []

    def set_mic_open(self, v):
        self.open.append(v)


class FakeSession(QObject):
    state_changed = Signal(str)
    countdown_tick = Signal(int)
    saved = Signal(object, int)
    compressing = Signal(object)
    failed = Signal(str)
    warning = Signal(str)

    def __init__(self, *a, **k):
        super().__init__()
        self.state = "idle"
        self.audio = FakeAudio()
        self.begun = None
        self.stopped = False

    def begin(self, countdown):
        self.begun = countdown
        self.state = "recording"
        self.state_changed.emit("recording")

    def stop(self):
        self.stopped = True
        self.state = "done"
        self.state_changed.emit("done")

    def elapsed_ms(self):
        return 0


class FakeWin(QObject):
    draw_mode_changed = Signal(bool)
    settings_changed = Signal(object)

    def __init__(self, *a, **k):
        super().__init__()
        self.shown = self.closed = False
        self.draw_mode = False

    def show(self):
        self.shown = True

    def close(self):
        self.closed = True

    def place(self, area):
        pass

    def show_count(self, n):
        self.count = n

    def set_draw_mode(self, on):
        self.draw_mode = on


class FakeHotkey:
    made = []

    def __init__(self, hotkey, cb):
        self.hotkey, self.cb = hotkey, cb
        self.started = self.stopped = False
        FakeHotkey.made.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def make(qapp, **kw):
    FakeHotkey.made = []
    s = Settings(**kw)
    tray = FakeTray()
    saved_settings, opened, made = [], [], {}

    def session_factory(*a, **k):
        made["session"] = FakeSession()
        return made["session"]

    keys = {"down": False}
    c = RecordingController(
        s, tray, saved_settings.append,
        session_factory=session_factory, layer_factory=FakeWin, frame_factory=FakeWin,
        bar_factory=lambda sess, settings, layer: FakeWin(), hotkey_factory=FakeHotkey,
        key_down=lambda hk: keys["down"], opener=opened.append, screen_for=lambda area: None,
    )
    mon = Monitor(1, 0, 0, 1920, 1080, Image.new("RGB", (4, 4)))
    return c, tray, made, saved_settings, opened, keys, mon


def test_active_while_recording_and_stop(qapp):
    c, tray, made, *_, mon = make(qapp)
    assert not c.active
    c.start(mon, QRect(0, 0, 100, 100), [])
    assert c.active and made["session"].begun is True and tray.recording == [True]
    c.stop()
    assert made["session"].stopped and not c.active and tray.recording == [True, False]


def test_saved_shows_tray_message_and_opens_folder(qapp):
    c, tray, made, _, opened, _, mon = make(qapp)
    c.start(mon, QRect(0, 0, 100, 100), [])
    made["session"].saved.emit(Path("C:/v/Parzprint_x.mp4"), 2_500_000)
    assert any("Parzprint_x.mp4" in m and "2,4 MB" in m for m in tray.messages)
    c.message_clicked()
    assert opened == [Path("C:/v/Parzprint_x.mp4")]


def test_failure_and_compressing_messages(qapp):
    c, tray, made, *_, mon = make(qapp)
    c.start(mon, QRect(0, 0, 100, 100), [])
    made["session"].compressing.emit(Path("a.mp4"))
    made["session"].failed.emit("disco cheio")
    assert any("Comprimindo" in m for m in tray.messages) and any("disco cheio" in m for m in tray.messages)


def test_shutdown_stops_recording_first(qapp):
    c, tray, made, *_, mon = make(qapp)
    c.start(mon, QRect(0, 0, 100, 100), [])
    c.shutdown(timeout_ms=200)
    assert made["session"].stopped


def test_ptt_opens_while_held_and_closes_when_released(qapp):
    c, tray, made, _, _, keys, mon = make(qapp, mic_mode="ptt")
    c.start(mon, QRect(0, 0, 100, 100), [])
    hk = FakeHotkey.made[-1]
    assert hk.hotkey == "Ctrl+Alt+Space" and hk.started
    keys["down"] = True
    hk.cb()
    c._ptt_pressed_main()
    assert made["session"].audio.open[-1] is True
    keys["down"] = False
    c._ptt_poll()
    assert made["session"].audio.open[-1] is False
    c.stop()
    assert hk.stopped


def test_no_ptt_hotkey_when_mode_is_always(qapp):
    c, tray, made, *_, mon = make(qapp, mic_mode="always")
    c.start(mon, QRect(0, 0, 100, 100), [])
    assert FakeHotkey.made == []


def test_bar_settings_are_saved(qapp):
    c, tray, made, saved, *_, mon = make(qapp)
    c.start(mon, QRect(0, 0, 100, 100), [])
    c.bar.settings_changed.emit(c.settings)
    assert saved == [c.settings]


def test_is_key_down_checks_every_part():
    down = {0x11, 0x12, 0x20}
    assert is_key_down("Ctrl+Alt+Space", state_fn=lambda vk: vk in down)
    assert not is_key_down("Ctrl+Alt+S", state_fn=lambda vk: vk in down)
