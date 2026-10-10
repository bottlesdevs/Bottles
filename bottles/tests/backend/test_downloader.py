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
        headers={}, raise_for_status=lambda: None, content=b"complete"
    )
    monkeypatch.setattr(downloader_module.requests, "get", lambda *a, **kw: response)

    assert Downloader(
        "https://example.org/dependency.exe", str(destination)
    ).download().ok
    assert destination.read_bytes() == b"complete"
    assert not destination.with_name("dependency.exe.part").exists()
