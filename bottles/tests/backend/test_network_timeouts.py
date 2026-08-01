from types import SimpleNamespace

import pycurl

from bottles.backend import downloader as downloader_module
from bottles.backend.downloader import Downloader
from bottles.backend.globals import Paths
from bottles.backend.managers import component as component_module
from bottles.backend.managers.component import ComponentManager
from bottles.backend.models.result import Result
from bottles.backend.repos import repo as repo_module
from bottles.backend.repos.repo import Repo
from bottles.backend.state import Status


class FakeCurl:
    URL = pycurl.URL
    FOLLOWLOCATION = pycurl.FOLLOWLOCATION
    HTTPHEADER = pycurl.HTTPHEADER
    NOBODY = pycurl.NOBODY
    WRITEDATA = pycurl.WRITEDATA
    RESPONSE_CODE = pycurl.RESPONSE_CODE
    EFFECTIVE_URL = pycurl.EFFECTIVE_URL

    def __init__(self, payload=b"entry: value\n", response_code=200):
        self.options = {}
        self.payload = payload
        self.response_code = response_code
        self.closed = False

    def setopt(self, option, value):
        self.options[option] = value

    def perform(self):
        if pycurl.WRITEDATA in self.options:
            self.options[pycurl.WRITEDATA].write(self.payload)

    def getinfo(self, option):
        if option == pycurl.RESPONSE_CODE:
            return self.response_code
        if option == pycurl.EFFECTIVE_URL:
            return self.options[pycurl.URL]
        return None

    def close(self):
        self.closed = True


def make_repo():
    repo = object.__new__(Repo)
    repo.url = "https://example.test"
    repo.name = "test"
    repo.offline = False
    return repo


def test_repository_catalog_request_has_timeouts(monkeypatch, tmp_path):
    curl = FakeCurl()
    monkeypatch.setattr(repo_module.pycurl, "Curl", lambda: curl)
    monkeypatch.setattr(Paths, "temp", str(tmp_path))

    repo = make_repo()
    catalog = Repo._Repo__get_catalog(repo, "https://example.test/index.yml")

    assert catalog == {"entry": "value"}
    assert curl.options[pycurl.CONNECTTIMEOUT] == 10
    assert curl.options[pycurl.TIMEOUT] == 30


def test_repository_manifest_request_has_timeouts(monkeypatch, tmp_path):
    curl = FakeCurl()
    monkeypatch.setattr(repo_module.pycurl, "Curl", lambda: curl)
    monkeypatch.setattr(Paths, "temp", str(tmp_path))

    repo = make_repo()
    manifest = Repo.get_manifest(repo, "https://example.test/manifest.yml")

    assert manifest == {"entry": "value"}
    assert curl.options[pycurl.CONNECTTIMEOUT] == 10
    assert curl.options[pycurl.TIMEOUT] == 30


def test_repository_closes_timed_out_request(monkeypatch, tmp_path):
    curl = FakeCurl()

    def timeout():
        raise pycurl.error(pycurl.E_OPERATION_TIMEDOUT, "timed out")

    curl.perform = timeout
    monkeypatch.setattr(repo_module.pycurl, "Curl", lambda: curl)
    monkeypatch.setattr(Paths, "temp", str(tmp_path))

    repo = make_repo()
    catalog = Repo._Repo__get_catalog(repo, "https://example.test/index.yml")

    assert catalog == {}
    assert curl.closed is True


def test_component_probe_has_timeouts(monkeypatch, tmp_path):
    curl = FakeCurl(response_code=503)
    monkeypatch.setattr(component_module.pycurl, "Curl", lambda: curl)
    monkeypatch.setattr(Paths, "temp", str(tmp_path))

    component = object.__new__(ComponentManager)
    component._ComponentManager__manager = SimpleNamespace(check_app_dirs=lambda: None)

    result = ComponentManager.download(
        component,
        "https://example.test/runner.tar.xz",
        "runner.tar.xz",
    )

    assert result.ok is False
    assert curl.options[pycurl.CONNECTTIMEOUT] == 10
    assert curl.options[pycurl.TIMEOUT] == 30


def test_stream_download_has_timeouts(monkeypatch, tmp_path):
    request = {}

    def get(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return SimpleNamespace(headers={}, content=b"runner")

    monkeypatch.setattr(downloader_module.requests, "get", get)

    result = Downloader(
        "https://example.test/runner.tar.xz",
        str(tmp_path / "runner.tar.xz"),
    ).download()

    assert result.ok is True
    assert request["timeout"] == (10, 30)


def test_stream_timeout_removes_partial_download(monkeypatch, tmp_path):
    class Response:
        headers = {"content-length": "8"}

        @staticmethod
        def iter_content(_size):
            yield b"half"
            raise downloader_module.requests.exceptions.ReadTimeout

    monkeypatch.setattr(
        downloader_module.requests, "get", lambda *_args, **_kwargs: Response()
    )
    destination = tmp_path / "runner.tar.xz"

    result = Downloader(
        "https://example.test/runner.tar.xz",
        str(destination),
    ).download()

    assert result.ok is False
    assert destination.exists() is False


def test_component_install_stops_after_extraction_failure(monkeypatch):
    manager = SimpleNamespace(
        check_dxvk=lambda: None,
        organize_components=lambda: None,
    )
    component = object.__new__(ComponentManager)
    component._ComponentManager__manager = manager
    manifest = {
        "File": [
            {
                "url": "https://example.test/dxvk.tar.xz",
                "file_name": "dxvk.tar.xz",
                "rename": "",
                "file_checksum": "",
            }
        ]
    }
    statuses = []

    monkeypatch.setattr(ComponentManager, "get_component", lambda *_args: manifest)
    monkeypatch.setattr(
        ComponentManager, "download", lambda *_args, **_kwargs: Result(True)
    )
    monkeypatch.setattr(ComponentManager, "extract", lambda *_args: False)

    result = ComponentManager.install(
        component,
        "dxvk",
        "dxvk-test",
        func=lambda **kwargs: statuses.append(kwargs["status"]),
    )

    assert result.ok is False
    assert statuses == [Status.FAILED]
