from types import SimpleNamespace

import pytest

from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.wine.uninstaller import Uninstaller


def test_reinstall_records_manifest_uninstaller():
    config = BottleConfig(Name="Bottle", Installed_Dependencies=["dotnet40"])

    def update_config(config, key, value, scope=""):
        if scope:
            config[scope][key] = value
        else:
            config[key] = value

    dependency_manager = DependencyManager.__new__(DependencyManager)
    dependency_manager._DependencyManager__manager = SimpleNamespace(
        update_config=update_config,
        versioning_manager=SimpleNamespace(create_state=lambda **_kwargs: None),
        supported_dependencies={},
    )
    dependency_manager.get_dependency = lambda _name: {
        "Dependencies": [],
        "Steps": [],
        "Uninstaller": "Microsoft .NET Framework 4 Extended",
    }

    result = dependency_manager.install(config, ("dotnet40", {}))

    assert result.ok
    assert result.data["uninstaller"]
    assert config.Uninstallers == {
        "dotnet40": "Microsoft .NET Framework 4 Extended"
    }


def test_dependency_without_uninstaller_cannot_be_removed():
    config = BottleConfig(
        Name="Bottle",
        Installed_Dependencies=["arial32"],
        Uninstallers={"arial32": "NO_UNINSTALLER"},
    )
    manager = SimpleNamespace(update_config=lambda *_args, **_kwargs: None)

    result = Manager.remove_dependency(manager, config, ("arial32", {}))

    assert not result.ok
    assert config.Installed_Dependencies == ["arial32"]


def test_dependency_with_uninstaller_is_removed(monkeypatch):
    removed = []
    config = BottleConfig(
        Name="Bottle",
        Installed_Dependencies=["dotnet40"],
        Uninstallers={"dotnet40": "Microsoft .NET Framework 4 Extended"},
    )

    def update_config(config, key, value, scope="", remove=False):
        if scope and remove:
            del config[scope][key]

    monkeypatch.setattr(
        Uninstaller,
        "from_name",
        lambda _self, name: removed.append(name) or Result(True),
    )
    manager = SimpleNamespace(update_config=update_config)

    result = Manager.remove_dependency(manager, config, ("dotnet40", {}))

    assert result.ok
    assert removed == ["Microsoft .NET Framework 4 Extended"]
    assert config.Installed_Dependencies == []
    assert config.Uninstallers == {}


@pytest.mark.parametrize("plural", [False, True])
def test_reinstall_records_all_manifest_uninstallers(plural):
    config = BottleConfig(Name="Bottle", Installed_Dependencies=["runtime"])
    names = ["Runtime Extended", "Runtime Client"]
    def update_config(config, key, value, scope=""):
        if scope:
            config[scope][key] = value
        else:
            config[key] = value
    manager = DependencyManager.__new__(DependencyManager)
    manager._DependencyManager__manager = SimpleNamespace(
        update_config=update_config,
        versioning_manager=SimpleNamespace(create_state=lambda **_kwargs: None),
        supported_dependencies={},
    )
    manifest = {"Dependencies": [], "Steps": [], "Uninstaller": names}
    if plural:
        manifest.update(Uninstaller=names[0], Uninstallers=names)
    manager.get_dependency = lambda _name: manifest

    assert manager.install(config, ("runtime", {})).ok
    assert config.Uninstallers["runtime"] == names


@pytest.mark.parametrize("fail_at", [None, 0, 1])
def test_dependency_removal_keeps_state_until_all_uninstallers_finish(monkeypatch, fail_at):
    names = ["Runtime Extended", "Runtime Client"]
    config = BottleConfig(Name="Bottle", Installed_Dependencies=["runtime"], Uninstallers={"runtime": names})
    removed = []
    def uninstall(_self, name):
        removed.append(name)
        assert config.Installed_Dependencies == ["runtime"]
        return Result(names.index(name) != fail_at)
    monkeypatch.setattr(Uninstaller, "from_name", uninstall)
    def update_config(config, key, value, scope="", remove=False):
        if scope and remove:
            del config[scope][key]
    manager = SimpleNamespace(update_config=update_config)

    result = Manager.remove_dependency(manager, config, ("runtime", {}))

    assert result.ok is (fail_at is None)
    assert removed == names[:2 if fail_at is None else fail_at + 1]
    assert config.Installed_Dependencies == ([] if fail_at is None else ["runtime"])
    assert config.Uninstallers == ({} if fail_at is None else {"runtime": names})
