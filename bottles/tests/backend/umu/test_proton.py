from pathlib import Path
from types import SimpleNamespace

import pytest

from bottles.backend.models.result import Result
from bottles.backend.umu import UmuGameRepository, UmuProtonCatalog


def _write_proton(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("toolmanifest.vdf").write_text(
        '"manifest"\n{\n    "commandline" "/proton run"\n}\n',
        encoding="utf-8",
    )


class Settings:
    def __init__(self, proton="UMU-Proton"):
        self.proton = proton

    def get_string(self, _key):
        return self.proton


class ComponentManager:
    def __init__(self, paths):
        self.paths = paths
        self.calls = []

    def install(self, component_type, component_name, **_kwargs):
        self.calls.append((component_type, component_name))
        _write_proton(self.paths[component_name])
        return Result(True)


def _manager(tmp_path, *, default="UMU-Proton"):
    paths = {
        "ge-proton-installed": tmp_path / "ge-proton-installed",
        "ge-proton-download": tmp_path / "ge-proton-download",
        "soda": tmp_path / "soda",
    }
    _write_proton(paths["ge-proton-installed"])
    paths["soda"].mkdir()
    manager = SimpleNamespace(
        runners_available=["soda", "ge-proton-installed"],
        external_runners=set(),
        supported_proton_runners={
            "ge-proton-installed": {"Channel": "stable", "Installed": True},
            "ge-proton-download": {"Channel": "stable"},
        },
        utils_conn=SimpleNamespace(status=True),
        settings=Settings(default),
        umu_repository=UmuGameRepository(tmp_path / "umu"),
    )
    manager.component_manager = ComponentManager(paths)
    return manager, paths


def test_validate_value_accepts_auto_tokens_and_proton_root(tmp_path):
    proton = tmp_path / "GE-Proton"
    _write_proton(proton)

    assert UmuProtonCatalog.validate_value("UMU-Proton") == "UMU-Proton"
    assert UmuProtonCatalog.validate_value("GE-Proton") == "GE-Proton"
    assert UmuProtonCatalog.validate_value(str(proton)) == str(proton)

    with pytest.raises(ValueError, match="not installed"):
        UmuProtonCatalog.validate_value(str(tmp_path / "missing"))


def test_catalog_lists_only_proton_runners(monkeypatch, tmp_path):
    manager, paths = _manager(tmp_path)
    monkeypatch.setattr(
        UmuProtonCatalog,
        "_runner_path",
        staticmethod(lambda name: str(paths[name])),
    )

    choices = UmuProtonCatalog(manager).list_choices()

    assert [choice.value for choice in choices[:2]] == ["UMU-Proton", "GE-Proton"]
    assert any(choice.component_name == "ge-proton-installed" for choice in choices)
    assert any(choice.component_name == "ge-proton-download" for choice in choices)
    assert not any(choice.component_name == "soda" for choice in choices)


def test_install_delegates_to_component_manager(monkeypatch, tmp_path):
    manager, paths = _manager(tmp_path)
    monkeypatch.setattr(
        UmuProtonCatalog,
        "_runner_path",
        staticmethod(lambda name: str(paths[name])),
    )
    catalog = UmuProtonCatalog(manager)

    result = catalog.install("ge-proton-download")

    assert result.ok is True
    assert result.data.value == str(paths["ge-proton-download"])
    assert manager.component_manager.calls == [
        ("runner:proton", "ge-proton-download")
    ]


def test_component_in_use_checks_default_and_games(monkeypatch, tmp_path):
    manager, paths = _manager(
        tmp_path,
        default=str(tmp_path / "ge-proton-installed"),
    )
    monkeypatch.setattr(
        UmuProtonCatalog,
        "_runner_path",
        staticmethod(lambda name: str(paths[name])),
    )

    assert UmuProtonCatalog(manager).component_in_use("ge-proton-installed") is True
