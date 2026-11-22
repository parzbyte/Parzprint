import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Uma QApplication antes de qualquer teste: um QCoreApplication criado antes
# impediria os testes que montam janelas.
_APP = QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def qapp():
    return _APP


def wait_until(cond, timeout_s: float = 3) -> bool:
    """Roda o laço de eventos do Qt até ``cond()`` valer ou o tempo acabar."""
    import time

    from PySide6.QtCore import QCoreApplication

    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return bool(cond())
