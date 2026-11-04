from threading import Event
from types import SimpleNamespace

import pytest
import requests

from bottles.backend import downloader as downloader_module
from bottles.backend.downloader import Downloader
from bottles.backend.globals import Paths
from bottles.backend.managers.component import is_cached_file


def test_interrupted_download_is_not_cached(tmp_path, monkeypatch):
    destination = tmp_path / "dependency.exe"

    def chunks(size):
        yield b"partial"
        raise SystemExit

    response = SimpleNamespace(
        headers={"content-length": "14"},
        raise_for_status=lambda: None,
        iter_content=chunks,
        close=lambda: None,
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)

    with pytest.raises(SystemExit):
        Downloader("https://example.org/dependency.exe", str(destination)).download()

    assert not destination.exists()
    monkeypatch.setattr(Paths, "temp", str(tmp_path))
    assert not is_cached_file(destination.name)
    response.headers["content-length"] = "8"
    response.iter_content = lambda size: iter([b"complete"])
    assert Downloader(
        "https://example.org/dependency.exe", str(destination)
    ).download().ok
    assert destination.read_bytes() == b"complete"
    assert is_cached_file(destination.name)
    assert not destination.with_name("dependency.exe.part").exists()


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_download_preserves_existing_file(tmp_path, monkeypatch, cancel):
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"previous")
    event = Event()
    if cancel:
        event.set()

    def chunks(size):
        yield b"partial"
        raise requests.ConnectionError("connection lost")

    response = SimpleNamespace(
        headers={"content-length": "14"},
        raise_for_status=lambda: None,
        iter_content=chunks,
        close=lambda: None,
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)

    assert not Downloader(
        "https://example.org/dependency.exe", str(destination), cancel_event=event
    ).download().ok
    assert destination.read_bytes() == b"previous"
    assert not destination.with_name("dependency.exe.part").exists()


def test_download_without_content_length(tmp_path, monkeypatch):
    destination = tmp_path / "dependency.exe"
    response = SimpleNamespace(
        headers={},
        raise_for_status=lambda: None,
        iter_content=lambda size: iter([b"complete"]),
        close=lambda: None,
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)

    assert Downloader(
        "https://example.org/dependency.exe", str(destination)
    ).download().ok
    assert destination.read_bytes() == b"complete"
    assert not destination.with_name("dependency.exe.part").exists()


@pytest.mark.parametrize("length,total", [
    ("8, 8", 8), ("08, 8", 8), ("unknown", 0), ("", 0), ("-8", 0), (None, 0),
])
def test_download_handles_repeated_or_invalid_content_length(tmp_path, monkeypatch, length, total):
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"previous")
    updates = []
    closed = []
    response = SimpleNamespace(
        headers={"content-length": length},
        raise_for_status=lambda: None,
        iter_content=lambda size: iter([b"complete"]),
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)
    result = Downloader(
        "https://example.org/dependency.exe", str(destination),
        update_func=lambda *args, **kwargs: updates.append((args, kwargs)),
    ).download()

    assert result.ok
    assert destination.read_bytes() == b"complete"
    assert not destination.with_name("dependency.exe.part").exists()
    assert updates == [((8, total) if total else (1, 1), {})]
    assert closed == [True]


def test_cancelled_download_does_not_start_request(tmp_path, monkeypatch):
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"previous")
    event = Event()
    event.set()

    def request(*args, **kwargs):
        pytest.fail("cancelled download started a request")

    monkeypatch.setattr(downloader_module.requests, "get", request)
    result = Downloader(
        "https://example.org/dependency.exe", str(destination), cancel_event=event
    ).download()

    assert not result.ok
    assert result.message == "cancelled"
    assert destination.read_bytes() == b"previous"
    assert not destination.with_name("dependency.exe.part").exists()


@pytest.mark.parametrize("length", [None, "14", "14, 14", "-14", "unknown"])
@pytest.mark.parametrize("at_end", [False, True])
def test_cancelled_stream_preserves_existing_file(tmp_path, monkeypatch, length, at_end):
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"previous")
    event = Event()
    closed = []
    updates = []

    def chunks(size):
        yield b"partial"
        event.set()
        if not at_end:
            yield b"cancelled"

    response = SimpleNamespace(
        headers={"content-length": length} if length else {},
        raise_for_status=lambda: None,
        iter_content=chunks,
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)
    result = Downloader(
        "https://example.org/dependency.exe",
        str(destination),
        cancel_event=event,
        update_func=lambda *args, **kwargs: updates.append((args, kwargs)),
    ).download()

    assert not result.ok
    assert result.message == "cancelled"
    assert destination.read_bytes() == b"previous"
    assert not destination.with_name("dependency.exe.part").exists()
    assert closed == [True]
    assert updates[-1] == ((), {"status": downloader_module.Status.CANCELLED})


def test_download_restarts_after_a_truncated_http_response(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    payload = b"Complete dependency payload" * 5000
    requests_seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests_seen.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload[:10000] if len(requests_seen) == 1 else payload)
            self.wfile.flush()
            self.close_connection = True

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"Previous dependency")
    try:
        result = Downloader(f"http://127.0.0.1:{server.server_port}/dependency.exe", str(destination)).download()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.ok
    assert requests_seen == ["/dependency.exe", "/dependency.exe"]
    assert destination.read_bytes() == payload
    assert not destination.with_suffix(".exe.part").exists()


@pytest.mark.parametrize("error", [requests.HTTPError("404"), requests.exceptions.SSLError("certificate")])
def test_download_does_not_retry_http_or_certificate_errors(tmp_path, monkeypatch, error):
    calls = []

    def get(*_args, **_kwargs):
        calls.append(True)
        raise error

    monkeypatch.setattr(downloader_module.requests, "get", get)
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"Previous dependency")

    assert not Downloader("https://example.test/dependency.exe", str(destination)).download().ok
    assert calls == [True]
    assert destination.read_bytes() == b"Previous dependency"
    assert not destination.with_suffix(".exe.part").exists()


def test_cancel_during_retry_delay_prevents_another_request(tmp_path, monkeypatch):
    event = Event()
    calls = []
    updates = []

    def get(*_args, **_kwargs):
        calls.append(True)
        event.set()
        raise requests.ReadTimeout("timeout")

    monkeypatch.setattr(downloader_module.requests, "get", get)
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"Previous dependency")
    result = Downloader("https://example.test/dependency.exe", str(destination), cancel_event=event,
                        update_func=lambda **kwargs: updates.append(kwargs)).download()

    assert not result.ok
    assert result.message == "cancelled"
    assert calls == [True]
    assert updates == [{"status": downloader_module.Status.CANCELLED}]
    assert destination.read_bytes() == b"Previous dependency"
    assert not destination.with_suffix(".exe.part").exists()


def test_download_stops_after_three_timeouts(tmp_path, monkeypatch):
    calls = []
    waits = []

    def get(*_args, **_kwargs):
        calls.append(True)
        raise requests.ReadTimeout("timeout")

    monkeypatch.setattr(downloader_module.requests, "get", get)
    monkeypatch.setattr(downloader_module.time, "sleep", waits.append)
    destination = tmp_path / "dependency.exe"
    destination.write_bytes(b"Previous dependency")

    result = Downloader("https://example.test/dependency.exe", str(destination)).download()

    assert not result.ok
    assert len(calls) == 3
    assert waits == [1, 2]
    assert destination.read_bytes() == b"Previous dependency"
    assert not destination.with_suffix(".exe.part").exists()


def test_cancel_after_commit_keeps_the_completed_download_successful(tmp_path, monkeypatch):
    event = Event()
    destination = tmp_path / "dependency.exe"
    response = SimpleNamespace(headers={}, raise_for_status=lambda: None,
                               iter_content=lambda _size: iter([b"Complete"]), close=lambda: None)
    monkeypatch.setattr(downloader_module.requests, "get", lambda *_args, **_kwargs: response)
    replace = downloader_module.os.replace

    def commit(source, target):
        replace(source, target)
        event.set()

    monkeypatch.setattr(downloader_module.os, "replace", commit)

    result = Downloader("https://example.test/dependency.exe", str(destination), cancel_event=event).download()

    assert result.ok
    assert destination.read_bytes() == b"Complete"
