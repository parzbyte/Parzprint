"""Ponto de entrada: ``parzprint`` / ``python -m parzprint`` [--capture | --settings]."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .single_instance import SingleInstance, parse_args

    argv = sys.argv[1:] if argv is None else argv
    action = parse_args(argv)
    qapp = QApplication(sys.argv[:1])
    qapp.setApplicationName("Parzprint")

    instance = SingleInstance()
    if not instance.try_acquire():
        instance.send(action)
        return 0

    from .app import App

    app = App(qapp, instance)
    if action != "none":
        QTimer.singleShot(300, lambda: app.handle_message(action))
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
