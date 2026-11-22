import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from parzprint.translate.google import (
    GoogleTranslator,
    Result,
    TranslateError,
    clip,
    parse,
    request_parts,
    web_url,
)
from tests.conftest import wait_until

FIXTURES = Path(__file__).parent / "fixtures" / "google"


def FIX(name):
    return (FIXTURES / name).read_bytes()


def test_parse_joins_chunks_and_detects():
    r = parse(FIX("en_pt.json"))
    assert r.text.startswith("Olá") and r.detected == "en"


def test_parse_blank_is_empty_not_error():
    assert parse(FIX("vazio.json")).text.strip() == ""


@pytest.mark.parametrize("raw", [b"[null]", b"[[[1]]]", b"  [[1]]", b'[["x"]]', b"[[", b"[]"])
def test_parse_bad_format(raw):
    with pytest.raises(TranslateError) as e:
        parse(raw)
    assert e.value.kind == "format"


@pytest.mark.parametrize("raw", [b"", b"<html><body>Antes de continuar</body></html>", b"{}", b"Too many requests"])
def test_parse_not_json_is_refused(raw):
    """Página de consentimento ou de limite com status 200 não é defeito de formato."""
    with pytest.raises(TranslateError) as e:
        parse(raw)
    assert e.value.kind == "refused"


def test_parse_skips_chunks_without_text():
    r = parse('[[["Olá ","Hello ",null],[null,null,"Halo"],["mundo","world",null]],null,"en"]'.encode())
    assert r == Result("Olá mundo", "en")


def test_translator_200_html_refused(server):
    server["body"] = b"<html>consentimento</html>"
    tr = GoogleTranslator(server["url"])
    done, fail = _spy(tr)
    rid = tr.translate("oi", "auto", "en")
    assert wait_until(lambda: done or fail)
    assert fail == [(rid, "refused")] and not done
    tr.shutdown()


def test_clip():
    assert clip("a" * 5001) == ("a" * 5000, True) and clip("oi") == ("oi", False)


def test_request_parts_posts_text_in_body():
    url, body = request_parts("a&b ç", "auto", "pt")
    q = parse_qs(url.query())
    assert q["client"] == ["gtx"] and q["sl"] == ["auto"] and q["tl"] == ["pt"] and q["dt"] == ["t"]
    assert parse_qs(body.decode())["q"] == ["a&b ç"]


def test_web_url_encodes():
    assert "text=a%26b" in web_url("a&b", "en", "pt")


@pytest.fixture
def server():
    state = {"status": 200, "delays": [], "body": FIX("en_pt.json"), "calls": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            i = state["calls"]
            state["calls"] += 1
            delays = state["delays"]
            time.sleep(delays[i] if i < len(delays) else 0)
            try:
                self.send_response(state["status"])
                self.send_header("Content-Length", str(len(state["body"])))
                self.end_headers()
                self.wfile.write(state["body"])
            except OSError:
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_address[1]}/translate_a/single"
    yield state
    httpd.shutdown()
    httpd.server_close()


def _spy(tr):
    done, fail = [], []
    tr.finished.connect(lambda i, r: done.append((i, r)))
    tr.failed.connect(lambda i, k: fail.append((i, k)))
    return done, fail


def test_translator_success(server):
    tr = GoogleTranslator(server["url"])
    done, fail = _spy(tr)
    rid = tr.translate("Hello world. How are you?", "en", "pt")
    assert wait_until(lambda: done or fail)
    assert not fail
    assert done[0][0] == rid and isinstance(done[0][1], Result)
    assert done[0][1].text.startswith("Olá")
    tr.shutdown()


def test_translator_429_refused(server):
    server["status"] = 429
    tr = GoogleTranslator(server["url"])
    done, fail = _spy(tr)
    rid = tr.translate("oi", "auto", "en")
    assert wait_until(lambda: done or fail)
    assert fail == [(rid, "refused")] and not done
    tr.shutdown()


def test_translator_timeout_network(server):
    server["delays"] = [2]
    tr = GoogleTranslator(server["url"], timeout_ms=300)
    done, fail = _spy(tr)
    rid = tr.translate("oi", "auto", "en")
    assert wait_until(lambda: done or fail)
    assert fail == [(rid, "network")] and not done
    tr.shutdown()


def test_translator_new_request_aborts_old(server):
    server["delays"] = [1, 0]
    tr = GoogleTranslator(server["url"])
    done, fail = _spy(tr)
    first = tr.translate("um", "auto", "en")
    second = tr.translate("dois", "auto", "en")
    assert second != first
    assert wait_until(lambda: done or fail)
    wait_until(lambda: False, timeout_s=1.3)
    assert [i for i, _ in done] == [second] and not fail
    tr.shutdown()


def test_translator_shutdown_emits_nothing(server):
    server["delays"] = [0.5]
    tr = GoogleTranslator(server["url"])
    done, fail = _spy(tr)
    tr.translate("oi", "auto", "en")
    tr.shutdown()
    wait_until(lambda: False, timeout_s=1)
    assert not done and not fail
