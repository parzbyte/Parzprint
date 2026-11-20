from PySide6.QtCore import QObject, QPoint, QRect, QSize, Signal

from parzprint.recording.frame import AreaFrame
from parzprint.recording.recordbar import RecordBar, bar_position
from parzprint.settings import Settings

MICS = [("m1", "Mic Um"), ("m2", "Mic Dois")]


class FakeAudio:
    def __init__(self):
        self.calls = []

    def set_mic(self, mic_id):
        self.calls.append(("mic", mic_id))

    def set_mic_open(self, v):
        self.calls.append(("open", v))

    def set_system_audio(self, v):
        self.calls.append(("sys", v))


class FakeSession(QObject):
    state_changed = Signal(str)
    warning = Signal(str)

    def __init__(self):
        super().__init__()
        self.audio = FakeAudio()
        self.state = "recording"
        self.ms = 0
        self.calls = []

    def elapsed_ms(self):
        return self.ms

    def pause(self):
        self.calls.append("pause")
        self.state = "paused"
        self.state_changed.emit("paused")

    def resume(self):
        self.calls.append("resume")
        self.state = "recording"
        self.state_changed.emit("recording")

    def stop(self):
        self.calls.append("stop")


class FakeLayer(QObject):
    draw_mode_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.draw_mode = False

    def set_draw_mode(self, on):
        self.draw_mode = on
        self.draw_mode_changed.emit(on)


def make_bar(qapp, **kw):
    s = Settings(mic_device="m1", **kw)
    sess, layer = FakeSession(), FakeLayer()
    bar = RecordBar(sess, s, layer, mics=MICS)
    saved = []
    bar.settings_changed.connect(saved.append)
    return bar, sess, layer, s, saved


def test_bar_starts_with_saved_choices(qapp):
    bar, *_ = make_bar(qapp, mic_mode="ptt", system_audio=False)
    assert bar.mic_combo.currentData() == "m1"
    assert bar.mode_combo.currentData() == "ptt"
    assert not bar.sys_button.isChecked()
    assert bar.mic_combo.itemData(bar.mic_combo.count() - 1) == ""


def test_bar_mode_menu_sets_mic_open(qapp):
    bar, sess, _, s, saved = make_bar(qapp)
    bar.mode_combo.setCurrentIndex(bar.mode_combo.findData("off"))
    assert ("open", False) in sess.audio.calls and s.mic_mode == "off" and saved


def test_bar_mic_switch_calls_set_mic(qapp):
    bar, sess, _, s, saved = make_bar(qapp)
    bar.mic_combo.setCurrentIndex(bar.mic_combo.findData("m2"))
    assert ("mic", "m2") in sess.audio.calls and s.mic_device == "m2" and saved
    bar.mic_combo.setCurrentIndex(bar.mic_combo.findData(""))
    assert ("mic", None) in sess.audio.calls


def test_bar_system_audio_toggle(qapp):
    bar, sess, _, s, _ = make_bar(qapp)
    bar.sys_button.click()
    assert ("sys", False) in sess.audio.calls and s.system_audio is False


def test_bar_pause_toggles_label(qapp):
    bar, sess, *_ = make_bar(qapp)
    bar.pause_button.click()
    assert sess.calls == ["pause"] and bar.pause_button.toolTip() == "Continuar"
    bar.pause_button.click()
    assert sess.calls == ["pause", "resume"] and bar.pause_button.toolTip() == "Pausar"


def test_bar_stop_and_draw(qapp):
    bar, sess, layer, *_ = make_bar(qapp)
    bar.draw_button.click()
    assert layer.draw_mode and bar.draw_button.isChecked()
    layer.set_draw_mode(False)
    assert not bar.draw_button.isChecked()
    bar.stop_button.click()
    assert sess.calls == ["stop"]


def test_bar_time_label(qapp):
    bar, sess, *_ = make_bar(qapp)
    sess.ms = 83_400
    bar.refresh()
    assert "01:23" in bar.time_label.text()


def test_bar_shows_warning(qapp):
    bar, sess, *_ = make_bar(qapp)
    sess.warning.emit("Microfone desconectado")
    assert "Microfone desconectado" in bar.warning_label.text() and not bar.warning_label.isHidden()


def test_bar_place_below_then_above_then_corner():
    screen, size = QRect(0, 0, 1920, 1080), QSize(500, 40)
    assert bar_position(QRect(100, 100, 800, 600), screen, size) == QPoint(100, 706)
    assert bar_position(QRect(100, 500, 800, 570), screen, size) == QPoint(100, 454)
    assert bar_position(screen, screen, size) == QPoint(1920 - 500 - 12, 1080 - 40 - 12)
    assert bar_position(QRect(1700, 100, 200, 200), screen, size).x() == 1920 - 500


def test_frame_shows_countdown_number(qapp):
    f = AreaFrame(QRect(100, 100, 400, 300))
    f.show_count(3)
    assert f.count == 3
    f.show_count(0)
    assert f.count == 0
    assert f.geometry().contains(QRect(100, 100, 400, 300))
    f.close()
