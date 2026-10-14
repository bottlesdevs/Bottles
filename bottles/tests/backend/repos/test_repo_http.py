from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from bottles.backend.repos.installer import InstallerRepo


@pytest.fixture
def repository_server(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.repos.repo.Paths.temp", str(tmp_path))
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    response = {"status": 200, "body": b"office:\n  Name: Office\n"}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect.yml":
                self.send_response(302)
                self.send_header("Location", "/index.yml")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(response["status"])
            self.send_header("Content-Length", str(len(response["body"])))
            self.end_headers()
            self.wfile.write(response["body"])

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    repository = object.__new__(InstallerRepo)
    repository.url = f"http://127.0.0.1:{server.server_port}"
    repository.index = f"{repository.url}/index.yml"
    repository.offline = False
    try:
        yield repository, response
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.mark.parametrize("status", [404, 429, 503])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("resource", ["catalog", "manifest", "plain_manifest"])
def test_http_failure_preserves_repository_cache(
    repository_server, tmp_path, status, cached, resource
):
    repository, response = repository_server
    plain = resource == "plain_manifest"

    def fetch():
        if resource == "catalog":
            return repository.refresh()
        return repository.get_manifest(f"{repository.url}/office.yml", plain=plain)

    expected = "office:\n  Name: Office\n" if plain else {"office": {"Name": "Office"}}
    if cached:
        assert fetch() == expected
    else:
        expected = {} if resource == "catalog" else False
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.yml")}
    response.update(status=status, body=b"error: Repository temporarily unavailable\n")

    assert fetch() == expected
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.yml")} == before


def test_repository_file_urls_remain_supported(monkeypatch, tmp_path):
    monkeypatch.setattr("bottles.backend.repos.repo.Paths.temp", str(tmp_path / "cache"))
    manifest = tmp_path / "office.yml"
    manifest.write_text("Name: Office\n")
    repository = object.__new__(InstallerRepo)
    repository.url = tmp_path.as_uri()
    repository.index = manifest.as_uri()
    repository.offline = False

    assert repository.refresh() == {"Name": "Office"}
    assert repository.get_manifest(manifest.as_uri()) == {"Name": "Office"}


def test_repository_http_redirects_remain_supported(repository_server):
    repository, _response = repository_server
    repository.index = f"{repository.url}/redirect.yml"

    assert repository.refresh() == {"office": {"Name": "Office"}}
    assert repository.get_manifest(repository.index) == {"office": {"Name": "Office"}}


def test_repository_recovers_after_http_failure(repository_server):
    repository, response = repository_server
    response.update(status=503, body=b"error: Repository temporarily unavailable\n")

    assert repository.refresh() == {}
    assert repository.get_manifest(f"{repository.url}/office.yml") is False
    response.update(status=200, body=b"office:\n  Name: Office\n")
    assert repository.refresh() == {"office": {"Name": "Office"}}
    assert repository.get_manifest(f"{repository.url}/office.yml") == {
        "office": {"Name": "Office"}
    }
