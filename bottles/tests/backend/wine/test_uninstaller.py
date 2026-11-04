from bottles.backend.models.result import Result
from bottles.backend.wine.uninstaller import Uninstaller

import pytest


def test_get_uuid_filters_uninstaller_output(monkeypatch):
    output = "\n".join(
        [
            "wineserver: using server-side synchronization.",
            "{MONO-RUNTIME}|||Wine Mono Runtime",
            "{GECKO}|||Wine Gecko (64-bit)",
            "{MONO-SUPPORT}|||Wine Mono Windows Support",
        ]
    )
    calls = []

    def launch(_self, **kwargs):
        calls.append(kwargs)
        return Result(True, output)

    monkeypatch.setattr(Uninstaller, "launch", launch)
    uninstaller = Uninstaller.__new__(Uninstaller)

    result = uninstaller.get_uuid("wine mono")

    assert result.data == "{MONO-SUPPORT}\n{MONO-RUNTIME}"
    assert calls == [
        {
            "args": "--list 2>&1",
            "communicate": True,
            "action_name": "get_uuid",
        }
    ]


def test_get_uuid_keeps_full_list(monkeypatch):
    output = "{MONO-RUNTIME}|||Wine Mono Runtime"
    monkeypatch.setattr(
        Uninstaller,
        "launch",
        lambda _self, **_kwargs: Result(True, output),
    )
    uninstaller = Uninstaller.__new__(Uninstaller)

    assert uninstaller.get_uuid().data == output


def test_from_uuid_waits_and_quotes_identifier(monkeypatch):
    calls = []

    def launch(_self, **kwargs):
        calls.append(kwargs)
        return Result(True)

    monkeypatch.setattr(Uninstaller, "launch", launch)
    uninstaller = Uninstaller.__new__(Uninstaller)

    uninstaller.from_uuid("{MONO-RUNTIME}; touch /tmp/uninstaller-injection")

    assert calls == [
        {
            "args": "--remove '{MONO-RUNTIME}; touch /tmp/uninstaller-injection'",
            "communicate": True,
            "action_name": "from_uuid",
        }
    ]


@pytest.mark.parametrize("query", [Result(False, message="query failed"), Result(True, ""), Result(True, "{FIRST}\n{SECOND}")])
@pytest.mark.parametrize("remove_ok", [False, True])
def test_from_name_reports_query_and_uninstaller_failures(monkeypatch, query, remove_ok):
    removed = []
    monkeypatch.setattr(Uninstaller, "get_uuid", lambda _self, _name: query)
    def remove(_self, uuid):
        removed.append(uuid)
        return Result(remove_ok)
    monkeypatch.setattr(Uninstaller, "from_uuid", remove)
    result = Uninstaller.__new__(Uninstaller).from_name("Runtime")

    assert result.ok is (query.ok and (not query.has_data or remove_ok))
    assert removed == (["{FIRST}", "{SECOND}"][:2 if remove_ok else 1] if query.ready else [])


@pytest.mark.parametrize("value,expected", [
    ("Runtime", ["Runtime"]),
    (["Runtime", "Client", "Runtime"], ["Runtime", "Client"]),
    (None, []), (False, []), ([], []),
    (["Runtime", None], []), (["Runtime", "NO_UNINSTALLER"], []),
])
def test_uninstaller_names_accept_legacy_and_list_values(value, expected):
    assert Uninstaller.get_names(value) == expected
