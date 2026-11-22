import subprocess
import sys
import uuid

from PySide6.QtCore import QCoreApplication, QElapsedTimer

from parzprint.single_instance import SingleInstance, parse_args


def test_parse_args():
    assert parse_args(["--capture"]) == "capture"
    assert parse_args(["--settings"]) == "settings"
    assert parse_args(["--translate"]) == "translate"
    assert parse_args([]) == "none"
    assert parse_args(["--algo-desconhecido"]) == "none"


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def test_single_instance_roundtrip():
    app = _app()
    name = f"parzprint-test-{uuid.uuid4().hex[:8]}"
    first = SingleInstance(name)
    assert first.try_acquire()
    got = []
    first.message_received.connect(got.append)
    code = (
        "import sys; from PySide6.QtCore import QCoreApplication; "
        "from parzprint.single_instance import SingleInstance; "
        "a = QCoreApplication([]); s = SingleInstance(sys.argv[1]); "
        "sys.exit(0 if (not s.try_acquire() and s.send('capture')) else 3)"
    )
    proc = subprocess.Popen([sys.executable, "-c", code, name])
    t = QElapsedTimer()
    t.start()
    while (not got or proc.poll() is None) and t.elapsed() < 10000:
        app.processEvents()
    assert proc.wait(5) == 0
    assert got == ["capture"]
    first.release()
