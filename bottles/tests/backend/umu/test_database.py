import io
import json
import urllib.error

import pytest

from bottles.backend.umu.database import (
    UmuDatabaseClient,
    UmuDatabaseEntry,
    UmuDatabaseError,
)


def _entry(**changes):
    value = {
        "title": "Baldur's Gate 3",
        "store": "gog",
        "codename": "1456460669",
        "umu_id": "umu-1086940",
        "acronym": "bg3",
        "notes": None,
        "exe_string": None,
    }
    value.update(changes)
    return value


def _opener(payload):
    data = json.dumps(payload).encode()
    return lambda _request, timeout: io.BytesIO(data)


def test_database_downloads_validated_entries_and_searches_locally(tmp_path):
    client = UmuDatabaseClient(
        tmp_path / "database.json",
        opener=_opener(
            [
                _entry(),
                _entry(
                    title="Borderlands 3",
                    store="egs",
                    codename="Catnip",
                    umu_id="umu-397540",
                    acronym="bl3",
                ),
            ]
        ),
    )

    entries = client.get_entries()

    assert len(entries) == 2
    assert client.search("bg3") == [entries[0]]
    assert client.search("catnip egs") == [entries[1]]
    assert json.loads((tmp_path / "database.json").read_text())[0]["title"] == (
        "Baldur's Gate 3"
    )


def test_database_uses_cached_entries_when_refresh_fails(tmp_path):
    cache = tmp_path / "database.json"
    cache.write_text(json.dumps([_entry()]))

    def offline(_request, timeout):
        raise urllib.error.URLError("offline")

    client = UmuDatabaseClient(cache, opener=offline)

    entries = client.get_entries(refresh=True)

    assert entries == (UmuDatabaseEntry.from_dict(_entry()),)


def test_database_reports_error_without_network_or_cache(tmp_path):
    def offline(_request, timeout):
        raise urllib.error.URLError("offline")

    client = UmuDatabaseClient(tmp_path / "missing.json", opener=offline)

    with pytest.raises(UmuDatabaseError):
        client.get_entries()


def test_database_skips_invalid_rows(tmp_path):
    client = UmuDatabaseClient(
        tmp_path / "database.json",
        opener=_opener([_entry(), _entry(store="unknown"), {"title": "Broken"}]),
    )

    assert client.get_entries() == (UmuDatabaseEntry.from_dict(_entry()),)
