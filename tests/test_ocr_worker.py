import subprocess
import sys

CODE = r"""
import time
from PIL import Image
from PySide6.QtCore import QCoreApplication
from parzprint.ocr_worker import OcrWorker

class Slow:
    name = "slow"
    def recognize(self, image):
        time.sleep(3)
        return []

app = QCoreApplication([])
w = OcrWorker(Slow(), Image.new("RGB", (4, 4)))
w.start()
time.sleep(0.2)
"""


def test_exit_while_ocr_running_does_not_crash():
    proc = subprocess.run([sys.executable, "-c", CODE], timeout=30)
    assert proc.returncode == 0


def test_worker_delivers_result(qapp):
    from PIL import Image
    from PySide6.QtCore import QElapsedTimer

    from parzprint.ocr.base import TextBlock
    from parzprint.ocr.fake import FakeEngine
    from parzprint.ocr_worker import OcrWorker

    got = []
    w = OcrWorker(FakeEngine([TextBlock("x", 0, 0, 1, 1)]), Image.new("RGB", (4, 4)))
    w.finished_ok.connect(got.append)
    w.start()
    t = QElapsedTimer()
    t.start()
    while not got and t.elapsed() < 3000:
        qapp.processEvents()
    assert got == [[TextBlock("x", 0, 0, 1, 1)]]
