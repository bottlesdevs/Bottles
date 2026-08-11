from types import SimpleNamespace

from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
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
        lambda _self, name: removed.append(name),
    )
    manager = SimpleNamespace(update_config=update_config)

    result = Manager.remove_dependency(manager, config, ("dotnet40", {}))

    assert result.ok
    assert removed == ["Microsoft .NET Framework 4 Extended"]
    assert config.Installed_Dependencies == []
    assert config.Uninstallers == {}
