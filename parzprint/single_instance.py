"""Instância única: a segunda execução repassa o pedido à primeira e sai."""

from __future__ import annotations

import argparse

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "parzprint-single-instance"
TIMEOUT_MS = 500


def parse_args(argv: list[str]) -> str:
    """"capture", "settings", "translate" ou "none"."""
    parser = argparse.ArgumentParser(prog="parzprint", add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--capture", action="store_true")
    group.add_argument("--settings", action="store_true")
    group.add_argument("--translate", action="store_true")
    try:
        args, _ = parser.parse_known_args(argv)
    except SystemExit:
        return "none"
    if args.capture:
        return "capture"
    if args.settings:
        return "settings"
    if args.translate:
        return "translate"
    return "none"


def _allow_foreground() -> None:
    """No Windows, deixa a instância aberta trazer a própria janela para a frente.

    Sem isso o Windows impede que um programa em segundo plano tome o foco, e a janela
    de configurações aberta por ``parzprint --settings`` ficaria atrás das outras.
    """
    import sys

    if sys.platform == "win32":
        import ctypes

        ASFW_ANY = -1
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)


class SingleInstance(QObject):
    message_received = Signal(str)

    def __init__(self, name: str = SERVER_NAME, parent=None):
        super().__init__(parent)
        self.name = name
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """True se esta é a primeira instância (e passa a escutar); False se já existe outra."""
        probe = QLocalSocket()
        probe.connectToServer(self.name)
        if probe.waitForConnected(TIMEOUT_MS):
            probe.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)  # sobra de uma execução que caiu (Unix)
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self.name):
            return False
        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def _on_connection(self) -> None:
        while self._server is not None and self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock: QLocalSocket) -> None:
        while sock.canReadLine():
            msg = bytes(sock.readLine()).decode("utf-8", "replace").strip()
            if msg:
                self.message_received.emit(msg)

    def send(self, message: str) -> bool:
        _allow_foreground()
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(TIMEOUT_MS):
            return False
        sock.write((message + "\n").encode("utf-8"))
        ok = sock.waitForBytesWritten(TIMEOUT_MS)
        sock.disconnectFromServer()
        return ok

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
