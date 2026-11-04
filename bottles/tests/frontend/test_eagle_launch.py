# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Gio

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip("Eagle launch tests require the Bottles resource bundle", allow_module_level=True)
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.frontend.views import eagle


@pytest.fixture
def launch(monkeypatch, tmp_path):
    config = BottleConfig(Name="Eagle fixture", Path=str(tmp_path), Environment="Custom")
    config.Parameters.gamemode = True
    config.Parameters.sync = "wine"
    saved = []
    executed = []
    toasts = []
    navigation = []
    manager = SimpleNamespace(_programs_cache={config.Name: object()})
    manager.update_config = lambda **kwargs: Manager.update_config(manager, **kwargs)
    view = SimpleNamespace(
        config=config, manager=manager,
        update_programs=lambda **kwargs: saved.append(kwargs),
    )
    details = SimpleNamespace(
        view_bottle=view,
        window=SimpleNamespace(show_toast=toasts.append),
        go_back_sidebar=lambda: navigation.append(True),
    )
    monkeypatch.setattr(eagle.ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path))
    monkeypatch.setattr(eagle, "RunAsync", lambda task, **_kwargs: task())

    def init(executor, **kwargs):
        executor.captured = kwargs
        executor.use_winebridge = True

    def run(executor):
        executed.append(executor.captured | {"winebridge": executor.use_winebridge})
        return Result(True)

    monkeypatch.setattr(eagle.WineExecutor, "__init__", init)
    monkeypatch.setattr(eagle.WineExecutor, "run", run)

    def invoke(suggestions=(), shipping=None, shipping_active=False):
        rows = [SimpleNamespace(
            suggestion_key=key, suggestion_value=value,
            get_active=lambda active=active: active,
        ) for key, value, active in suggestions]
        for index, row in enumerate(rows):
            row.get_next_sibling = lambda index=index: rows[index+1] if index+1 < len(rows) else None
        warning = None if shipping is None else SimpleNamespace(
            _ue_shipping_exe=shipping,
            get_active=lambda: shipping_active,
            get_next_sibling=lambda: None,
        )
        panel = SimpleNamespace(
            analysis_results={"name": "Fixture"},
            target_path=str(tmp_path / "App with spaces.exe"), details=details,
            list_suggestions=SimpleNamespace(get_first_child=lambda: rows[0] if rows else None),
            list_warnings=SimpleNamespace(get_first_child=lambda: warning),
        )
        eagle.EagleView._EagleView__on_launch_clicked(panel, None)
        return panel

    return SimpleNamespace(invoke=invoke, config=config, saved=saved, executed=executed,
                           toasts=toasts, navigation=navigation, manager=manager, view=view, root=tmp_path)


def test_eagle_saves_and_passes_selected_program_options(launch):
    launch.invoke([
        ("dxvk", True, True),
        ("dxvk", False, True),
        ("gamemode", False, True),
        ("sync", "esync", True),
        ("intel_env:FIXTURE", "two words", True),
        ("intel_env:UNSELECTED", "omit", False),
        ("intel_dll:first", "n,b", True),
        ("intel_dll:second", "b", True),
        ("intel_arg:0", '--title="two words"', True),
        ("intel_arg:1", "--fixture", True),
        ("intel_arg:2", "--omit", False),
    ])
    loaded = BottleConfig.load(str(launch.root / "bottle.yml"))
    assert loaded.status
    assert loaded.data.Parameters.gamemode is True
    assert loaded.data.Parameters.sync == "wine"
    program, = loaded.data.External_Programs.values()
    assert program["path"] == str(launch.root / "App with spaces.exe")
    assert program["folder"] == str(launch.root)
    assert program["name"] == "App with spaces"
    assert program["dxvk"] is False
    assert program["gamemode"] is False
    assert program["arguments"] == '--title="two words" --fixture'
    assert program["environment"] == {"FIXTURE": "two words", "WINEDLLOVERRIDES": "first=n,b;second=b"}
    assert launch.executed[0]["program_dxvk"] is False
    assert launch.executed[0]["environment"] == program["environment"]
    assert launch.executed[0]["args"] == program["arguments"]
    assert launch.executed[0]["config"].Parameters.gamemode is False
    assert launch.executed[0]["config"].Parameters.sync == "esync"
    assert launch.executed[0]["winebridge"] is False
    assert launch.config.Parameters.gamemode is True
    assert launch.config.Parameters.sync == "wine"
    assert launch.config.Name not in launch.manager._programs_cache
    assert launch.saved[0]["force_add"] == program
    assert len(launch.toasts) == len(launch.navigation) == 1


@pytest.mark.parametrize("active", [False, True])
def test_eagle_uses_selected_shipping_executable(launch, active):
    shipping = str(launch.root / "Shipping" / "Fixture.exe")
    panel = launch.invoke(shipping=shipping, shipping_active=active)
    expected = shipping if active else panel.target_path

    assert launch.executed[0]["exec_path"] == expected
    program, = launch.view.config.External_Programs.values()
    assert program["path"] == expected
    assert program["folder"] == str(Path(expected).parent)


def test_eagle_does_not_launch_after_failed_save(launch, monkeypatch):
    monkeypatch.setattr(BottleConfig, "dump", lambda *_args, **_kwargs: Result(False, message="Fixture write failed"))
    launch.invoke()

    assert launch.executed == []
    assert launch.saved == []
    assert launch.navigation == []
    assert launch.config.External_Programs == {}
    assert launch.config.Name in launch.manager._programs_cache
    assert launch.toasts == ["Could not save the program: Fixture write failed"]


def test_eagle_preserves_existing_programs_on_write_error(launch, monkeypatch):
    launch.config.External_Programs["existing"] = {"name": "Existing", "path": "existing.exe"}
    original = launch.config.to_dict()
    previous = launch.root / "previous.yml"
    assert launch.config.dump(str(previous)).status
    previous_bytes = previous.read_bytes()
    blocked = launch.root / "not-a-directory"
    blocked.write_text("Own write-error fixture")
    monkeypatch.setattr(eagle.ManagerUtils, "get_bottle_path", lambda _config: str(blocked))
    launch.invoke()

    assert launch.executed == launch.saved == launch.navigation == []
    assert launch.config.to_dict() == original
    assert previous.read_bytes() == previous_bytes
    assert launch.toasts[0].startswith("Could not save the program: ")


def test_eagle_retry_saves_one_new_program(launch, monkeypatch):
    dump = BottleConfig.dump
    monkeypatch.setattr(BottleConfig, "dump", lambda *_args, **_kwargs: Result(False, message="Retry fixture"))
    launch.invoke()
    assert launch.config.External_Programs == {}
    monkeypatch.setattr(BottleConfig, "dump", dump)
    launch.invoke([("intel_env:OMIT", "value", False), ("intel_arg:0", "--omit", False)])
    loaded = BottleConfig.load(str(launch.root / "bottle.yml"))

    assert loaded.status
    assert loaded.data.Parameters.gamemode is True
    assert loaded.data.Parameters.sync == "wine"
    program, = loaded.data.External_Programs.values()
    assert "environment" not in program
    assert "arguments" not in program
    assert len(launch.saved) == len(launch.executed) == len(launch.navigation) == 1
