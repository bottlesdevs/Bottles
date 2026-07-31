from bottles.backend.models.result import Result
from bottles.backend.wine.uninstaller import Uninstaller


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
