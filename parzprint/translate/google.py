"""Pedido e resposta do Google Tradutor, sem travar a tela."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from PySide6.QtCore import QByteArray, QObject, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

MAX_CHARS = 5000
TIMEOUT_MS = 8000
BASE_URL = "https://translate.googleapis.com/translate_a/single"


@dataclass(frozen=True)
class Result:
    text: str
    detected: str | None


class TranslateError(Exception):
    """``kind`` é "network", "refused" ou "format"."""

    def __init__(self, kind: str, message: str = ""):
        super().__init__(message or kind)
        self.kind = kind


def clip(text: str) -> tuple[str, bool]:
    """Corta em MAX_CHARS e diz se cortou."""
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS], True
    return text, False


def request_parts(
    text: str, source: str, target: str, base_url: str = BASE_URL
) -> tuple[QUrl, bytes]:
    """Endereço com os parâmetros e corpo do POST com o texto."""
    url = QUrl(base_url)
    query = QUrlQuery()
    for key, value in (("client", "gtx"), ("sl", source), ("tl", target), ("dt", "t")):
        query.addQueryItem(key, value)
    url.setQuery(query)
    return url, urlencode({"q": text}).encode()


def parse(raw: bytes) -> Result:
    """Junta os trechos traduzidos e lê o idioma detectado."""
    try:
        data = json.loads(raw)
        parts = [chunk[0] for chunk in data[0]]
        if not all(isinstance(part, str) for part in parts):
            raise TypeError("trecho sem texto")
        detected = data[2] if len(data) > 2 else None
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise TranslateError("format", str(exc)) from exc
    if not isinstance(detected, str):
        detected = None
    return Result("".join(parts), detected)


def web_url(text: str, source: str, target: str) -> str:
    return (
        f"https://translate.google.com/?sl={source}&tl={target}"
        f"&text={quote(text, safe='')}&op=translate"
    )


class GoogleTranslator(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self, base_url: str = BASE_URL, timeout_ms: int = TIMEOUT_MS, parent=None
    ):
        super().__init__(parent)
        self._base_url = base_url
        self._timeout_ms = timeout_ms
        self._manager = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._last_id = 0
        self._closed = False

    def translate(self, text: str, source: str, target: str) -> int:
        """Cancela o pedido anterior, envia este e devolve o id."""
        self._last_id += 1
        request_id = self._last_id
        self._drop_reply()
        if self._closed:
            return request_id
        url, body = request_parts(text, source, target, self._base_url)
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0")
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/x-www-form-urlencoded",
        )
        request.setTransferTimeout(self._timeout_ms)
        reply = self._manager.post(request, QByteArray(body))
        self._reply = reply
        reply.setProperty("request_id", request_id)
        reply.finished.connect(self._on_finished)
        return request_id

    def shutdown(self) -> None:
        """Cancela o que está em andamento e não emite mais nada."""
        self._closed = True
        self._drop_reply()

    def _drop_reply(self) -> None:
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()

    def _on_finished(self) -> None:
        reply = self.sender()
        request_id = reply.property("request_id")
        stale = self._closed or request_id != self._last_id
        if self._reply is reply:
            self._reply = None
        raw = bytes(reply.readAll())
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error = reply.error()
        reply.deleteLater()
        if stale:
            return
        if isinstance(status, int) and status >= 400:
            self.failed.emit(request_id, "refused")
        elif error != QNetworkReply.NetworkError.NoError:
            self.failed.emit(request_id, "network")
        else:
            try:
                result = parse(raw)
            except TranslateError as exc:
                self.failed.emit(request_id, exc.kind)
            else:
                self.finished.emit(request_id, result)
