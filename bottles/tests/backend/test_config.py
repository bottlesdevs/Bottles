from io import StringIO

import pytest

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.samples import Samples
from bottles.backend.wine.winecommand import WineEnv


def _reload(config):
    stream = StringIO()
    assert config.dump(stream).status is True
    stream.seek(0)
    result = BottleConfig.load(stream)
    assert result.status is True
    return result.data


@pytest.mark.parametrize(
    "excluded_defaults",
    [
        ["XMODIFIERS"],
        ["MANGOHUD_CONFIG", "XMODIFIERS"],
    ],
)
def test_load_migrates_default_inherited_environment(monkeypatch, excluded_defaults):
    legacy_defaults = [
        name
        for name in Samples.default_inherited_environment
        if name not in excluded_defaults
    ]
    config = BottleConfig(
        Limit_System_Environment=True,
        Inherited_Environment_Variables=legacy_defaults,
    )
    monkeypatch.setenv("XMODIFIERS", "@im=fcitx")

    loaded = _reload(config)
    env = WineEnv(allowed_keys=loaded.Inherited_Environment_Variables)

    assert env.get()["envs"]["XMODIFIERS"] == "@im=fcitx"


@pytest.mark.parametrize(
    "limit_environment,inherited",
    [
        (False, []),
        (True, ["DISPLAY"]),
        (True, ["DISPLAY", "CUSTOM_VARIABLE"]),
    ],
)
def test_load_preserves_custom_inherited_environment(limit_environment, inherited):
    config = BottleConfig(
        Limit_System_Environment=limit_environment,
        Inherited_Environment_Variables=inherited,
    )

    loaded = _reload(config)

    assert loaded.Inherited_Environment_Variables == inherited


def test_load_discards_legacy_component_update_preference():
    result = BottleConfig._fill_with(
        {"Parameters": {"show_component_updates": False}}
    )

    assert result.ok
    assert "show_component_updates" not in result.data.Parameters
