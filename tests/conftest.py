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
