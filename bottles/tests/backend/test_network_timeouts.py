from pathlib import Path
from types import SimpleNamespace

import pycurl
import pytest

from bottles.backend import downloader as downloader_module
from bottles.backend.downloader import Downloader
from bottles.backend.globals import Paths
from bottles.backend.managers import component as component_module
from bottles.backend.managers import repository as repository_module
from bottles.backend.managers.component import ComponentManager
from bottles.backend.managers.repository import RepositoryManager
from bottles.backend.models.result import Result
from bottles.backend.repos import repo as repo_module
from bottles.backend.repos.component import ComponentRepo
from bottles.backend.repos.repo import Repo
from bottles.backend.state import Signals, Status
from bottles.backend.utils import connection as connection_module
from bottles.backend.utils.connection import ConnectionUtils


class FakeCurl:
    URL = pycurl.URL
    FOLLOWLOCATION = pycurl.FOLLOWLOCATION
    HTTPHEADER = pycurl.HTTPHEADER
    NOBODY = pycurl.NOBODY
    NOPROGRESS = pycurl.NOPROGRESS
    XFERINFOFUNCTION = pycurl.XFERINFOFUNCTION
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


def test_connection_check_uses_reachable_bottles_service(monkeypatch):
    curl = FakeCurl()
    monkeypatch.setattr(connection_module.pycurl, "Curl", lambda: curl)
    connection = ConnectionUtils()

    assert connection.check_connection() is True
    assert curl.options[pycurl.URL] == (
        "https://proxy.usebottles.com/repo/components/"
    )
    assert curl.options[pycurl.USERAGENT].startswith("Bottles/")


def test_connection_check_retries_ipv4(monkeypatch):
    curl = FakeCurl()
    attempts = 0

    def perform():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise pycurl.error(pycurl.E_COULDNT_CONNECT, "unreachable")

    curl.perform = perform
    monkeypatch.setattr(connection_module.pycurl, "Curl", lambda: curl)
    connection = ConnectionUtils()

    assert connection.check_connection() is True
    assert attempts == 2
    assert curl.options[pycurl.IPRESOLVE] == pycurl.IPRESOLVE_V4


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


def test_component_download_uses_stream_downloader(monkeypatch, tmp_path):
    request = {}

    class DownloadStub:
        def __init__(self, **kwargs):
            request.update(kwargs)

        def download(self):
            Path(request["file"]).write_bytes(b"runner")
            return Result(True)

    monkeypatch.setattr(component_module, "Downloader", DownloadStub)
    monkeypatch.setattr(Paths, "temp", str(tmp_path))

    component = object.__new__(ComponentManager)
    component._ComponentManager__manager = SimpleNamespace(check_app_dirs=lambda: None)

    result = ComponentManager.download(
        component,
        "https://example.test/runner.tar.xz",
        "runner.tar.xz",
    )

    assert result.ok is True
    assert request["url"] == "https://example.test/runner.tar.xz"


def test_stream_download_has_timeouts(monkeypatch, tmp_path):
    request = {}

    def get(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return SimpleNamespace(
            headers={}, content=b"runner", raise_for_status=lambda: None
        )

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
        def raise_for_status():
            return None

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


class IndexCurl:
    URL = pycurl.URL
    FOLLOWLOCATION = pycurl.FOLLOWLOCATION
    CONNECTTIMEOUT = pycurl.CONNECTTIMEOUT
    TIMEOUT = pycurl.TIMEOUT
    NOPROGRESS = pycurl.NOPROGRESS
    XFERINFOFUNCTION = pycurl.XFERINFOFUNCTION
    WRITEDATA = pycurl.WRITEDATA
    RESPONSE_CODE = pycurl.RESPONSE_CODE

    def __init__(self, outcomes, requests):
        self.options = {}
        self.outcomes = outcomes
        self.requests = requests
        self.response_code = 0
        self.closed = False

    def setopt(self, option, value):
        self.options[option] = value

    def perform(self):
        url = self.options[pycurl.URL]
        self.requests.append(url)
        outcome = self.outcomes.get(url, 404)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            self.response_code, payload = outcome
            if pycurl.WRITEDATA in self.options:
                self.options[pycurl.WRITEDATA].write(payload)
        else:
            self.response_code = outcome

    def getinfo(self, option):
        if option == pycurl.RESPONSE_CODE:
            return self.response_code
        return None

    def close(self):
        self.closed = True


class ImmediateAsync:
    def __init__(self, task_func, **kwargs):
        task_func(**kwargs)

    def join(self):
        pass


class IPv4RetryCurl(IndexCurl):
    def __init__(self, requests):
        super().__init__({}, requests)
        self.attempt = 0

    def perform(self):
        self.requests.append(
            (self.options[pycurl.URL], self.options.get(pycurl.IPRESOLVE))
        )
        self.attempt += 1
        if self.attempt == 1:
            raise pycurl.error(
                pycurl.E_OPERATION_TIMEDOUT,
                "Resolving timed out after 5000 milliseconds",
            )

        self.response_code = 200
        self.options[pycurl.WRITEDATA].write(b"entry:\n  Category: test\n")


def make_repository_manager(monkeypatch, personal_repositories=None):
    signals = []
    for env_var in (
        "PERSONAL_COMPONENTS",
        "PERSONAL_DEPENDENCIES",
        "PERSONAL_INSTALLERS",
    ):
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setattr(
        repository_module,
        "DataManager",
        lambda: SimpleNamespace(get=lambda _key: personal_repositories or {}),
    )
    monkeypatch.setattr(repository_module.SignalManager, "connect", lambda *_args: None)
    monkeypatch.setattr(
        repository_module.SignalManager,
        "send",
        lambda signal, result: signals.append((signal, result)),
    )
    monkeypatch.setattr(repository_module, "RunAsync", ImmediateAsync)
    monkeypatch.setattr(repository_module, "APP_VERSION", "64.1")
    return RepositoryManager(get_index=False), signals


def keep_component_repository(manager):
    repositories = manager._RepositoryManager__repositories
    repository = repositories["components"]
    manager._RepositoryManager__repositories = {"components": repository}
    return repository


def test_repository_index_uses_immutable_github_fallback(monkeypatch, tmp_path):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    primary, fallback = repository["sources"]
    outcomes = {
        f"{primary}64.1.yml": pycurl.error(pycurl.E_OPERATION_TIMEDOUT, "timed out"),
        f"{fallback}64.1.yml": 404,
        f"{fallback}index.yml": (200, b"runtime-0.6.3:\n  Category: runtimes\n"),
    }
    requests = []
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: IndexCurl(outcomes, requests),
    )

    manager._RepositoryManager__get_index()

    index_requests = [
        f"{primary}64.1.yml",
        f"{primary}64.1.yml",
        f"{fallback}64.1.yml",
        f"{fallback}index.yml",
    ]
    assert requests == index_requests
    assert repository["url"] == fallback
    assert repository["index"] == f"{fallback}index.yml"
    assert repository["catalog"] == b"runtime-0.6.3:\n  Category: runtimes\n"
    assert len(signals) == 1
    assert signals[0][0] == Signals.RepositoryFetched
    assert signals[0][1].ok is True

    monkeypatch.setattr(Paths, "temp", str(tmp_path))
    repo = manager.get_repo("components")
    assert repo.url == fallback
    assert repo.catalog == {"runtime-0.6.3": {"Category": "runtimes"}}
    assert requests == index_requests
    manifest_url = f"{fallback}/runtimes/runtime-0.6.3.yml"
    manifest_data = b"Name: Runtime\n"
    outcomes[manifest_url] = (200, manifest_data)
    assert repo.get("runtime-0.6.3") == {"Name": "Runtime"}
    assert requests == [*index_requests, manifest_url]
    cache_files = list(tmp_path.glob("repositories/components/*/catalog.yml"))
    assert len(cache_files) == 1
    assert cache_files[0].read_bytes() == repository["catalog"]

    offline_repo = object.__new__(ComponentRepo)
    offline_repo.url = primary
    offline_repo.cache_url = primary
    offline_repo.offline = True
    offline_repo.catalog = Repo._Repo__get_catalog(offline_repo, "", offline=True)
    assert offline_repo.catalog == repo.catalog
    assert offline_repo.get("runtime-0.6.3") == {"Name": "Runtime"}
    assert requests == [*index_requests, manifest_url]


def test_repository_index_keeps_primary_when_available(monkeypatch):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    primary = repository["sources"][0]
    requests = []
    curl = IndexCurl(
        {f"{primary}64.1.yml": (200, b"entry:\n  Category: test\n")}, requests
    )
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: curl,
    )

    manager._RepositoryManager__get_index()

    assert requests == [f"{primary}64.1.yml"]
    assert repository["url"] == primary
    assert repository["index"] == f"{primary}64.1.yml"
    assert repository["catalog"] == b"entry:\n  Category: test\n"
    assert len(signals) == 1
    assert signals[0][1].ok is True
    assert pycurl.NOBODY not in curl.options
    assert curl.options[pycurl.CONNECTTIMEOUT] == 5
    assert curl.options[pycurl.TIMEOUT] == 10
    assert curl.closed is True


def test_repository_index_retries_resolution_timeout_with_ipv4(monkeypatch):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    url = f"{repository['sources'][0]}64.1.yml"
    requests = []
    curl = IPv4RetryCurl(requests)
    monkeypatch.setattr(repository_module.pycurl, "Curl", lambda: curl)

    manager._RepositoryManager__get_index()

    assert requests == [(url, None), (url, pycurl.IPRESOLVE_V4)]
    assert repository["catalog"] == b"entry:\n  Category: test\n"
    assert len(signals) == 1
    assert signals[0][1].ok is True


def test_repository_index_falls_back_after_truncated_transfer(monkeypatch):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    primary, fallback = repository["sources"]
    outcomes = {
        f"{primary}64.1.yml": 404,
        f"{primary}index.yml": pycurl.error(
            pycurl.E_PARTIAL_FILE, "transfer closed with bytes remaining"
        ),
        f"{fallback}64.1.yml": 404,
        f"{fallback}index.yml": (200, b"entry:\n  Category: test\n"),
    }
    requests = []
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: IndexCurl(outcomes, requests),
    )

    manager._RepositoryManager__get_index()

    assert requests == list(outcomes)
    assert repository["url"] == fallback
    assert repository["catalog"] == b"entry:\n  Category: test\n"
    assert len(signals) == 1
    assert signals[0][1].ok is True


def test_personal_repository_is_exclusive_and_instance_local(monkeypatch):
    custom = "https://mirror.example.test/components/"
    manager, signals = make_repository_manager(monkeypatch, {"components": custom})
    repository = keep_component_repository(manager)
    outcomes = {f"{custom}64.1.yml": 403}
    requests = []
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: IndexCurl(outcomes, requests),
    )

    manager._RepositoryManager__get_index()

    assert requests == list(outcomes)
    assert repository["sources"] == [custom]
    assert repository["url"] == custom
    assert repository["cache_url"] == custom
    assert len(signals) == 1
    assert signals[0][1].ok is False

    clean_manager, _signals = make_repository_manager(monkeypatch)
    clean_repository = clean_manager._RepositoryManager__repositories["components"]
    assert clean_repository["url"] == "https://proxy.usebottles.com/repo/components/"
    assert clean_repository["cache_url"] == clean_repository["url"]


def test_default_repository_fallbacks_are_commit_pinned(monkeypatch):
    manager, _signals = make_repository_manager(monkeypatch)
    repositories = manager._RepositoryManager__repositories

    assert repositories["components"]["sources"][1] == (
        "https://raw.githubusercontent.com/bottlesdevs/components/"
        "f63f670e12f015003b3f751cd53777377d9ec725/"
    )
    assert repositories["dependencies"]["sources"][1] == (
        "https://raw.githubusercontent.com/bottlesdevs/dependencies/"
        "2c0c19707c252d9ec49f1bf26ac4793fd041332b/"
    )
    assert repositories["installers"]["sources"][1] == (
        "https://raw.githubusercontent.com/bottlesdevs/programs/"
        "d1160b816ca44a1cc803ab9a0050071517cc1960/"
    )


@pytest.mark.parametrize(
    "outcome",
    (403, (200, b"invalid catalog")),
    ids=("forbidden", "invalid-yaml"),
)
def test_repository_index_uses_fallback_after_bad_primary(monkeypatch, outcome):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    primary, fallback = repository["sources"]
    catalog = b"entry:\n  Category: test\n"
    outcomes = {
        f"{primary}64.1.yml": outcome,
        f"{fallback}64.1.yml": 404,
        f"{fallback}index.yml": (200, catalog),
    }
    requests = []
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: IndexCurl(outcomes, requests),
    )

    manager._RepositoryManager__get_index()

    assert requests == list(outcomes)
    assert repository["url"] == fallback
    assert repository["catalog"] == catalog
    assert len(signals) == 1
    assert signals[0][1].ok is True


@pytest.mark.parametrize(
    "primary_outcome,fallback_outcome",
    (
        (
            pycurl.error(pycurl.E_COULDNT_CONNECT, "blocked"),
            pycurl.error(pycurl.E_COULDNT_CONNECT, "offline"),
        ),
        (403, (200, b"invalid catalog")),
    ),
    ids=("network-errors", "invalid-candidates"),
)
def test_repository_index_reports_one_failure_after_all_sources(
    monkeypatch, primary_outcome, fallback_outcome
):
    manager, signals = make_repository_manager(monkeypatch)
    repository = keep_component_repository(manager)
    primary, fallback = repository["sources"]
    outcomes = {
        f"{primary}64.1.yml": primary_outcome,
        f"{fallback}64.1.yml": fallback_outcome,
    }
    requests = []
    monkeypatch.setattr(
        repository_module.pycurl,
        "Curl",
        lambda: IndexCurl(outcomes, requests),
    )

    manager._RepositoryManager__get_index()

    if isinstance(primary_outcome, pycurl.error):
        assert requests == [
            f"{primary}64.1.yml",
            f"{primary}64.1.yml",
            f"{fallback}64.1.yml",
            f"{fallback}64.1.yml",
        ]
    else:
        assert requests == list(outcomes)
    assert repository["catalog"] is None
    assert len(signals) == 1
    assert signals[0][1].ok is False
