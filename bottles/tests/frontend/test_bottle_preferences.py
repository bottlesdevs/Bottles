from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import Gio

from bottles.backend.models.config import BottleConfig

resource_path = Path("/app/share/bottles/bottles.gresource")
if not resource_path.exists():
    pytest.skip(
        "Bottle preferences tests require the Bottles Flatpak runtime",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))


def _make_view(config):
    return SimpleNamespace(config=config, switch_hdr=Mock())


def test_flatpak_addons_use_the_current_runtime_branch():
    from bottles.frontend.views.bottle_preferences import FLATPAK_INSTALL_COMMANDS

    assert set(FLATPAK_INSTALL_COMMANDS) == {
        "gamescope",
        "hdr",
        "vkbasalt",
        "lsfg_vk",
        "mangohud",
        "obsvkc",
    }
    assert all("remote-add" not in command for command in FLATPAK_INSTALL_COMMANDS.values())
    assert all(command.endswith("//25.08") for command in FLATPAK_INSTALL_COMMANDS.values())
    assert (
        "org.freedesktop.Platform.VulkanLayer.OBSVkCapture"
        in FLATPAK_INSTALL_COMMANDS["obsvkc"]
    )


def test_active_hdr_remains_available_to_disable_on_x11(monkeypatch):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig()
    config.Parameters.hdr = True
    view = _make_view(config)
    monkeypatch.setattr(
        bottle_preferences.DisplayUtils, "display_server_type", lambda: "x11"
    )

    PreferencesView._PreferencesView__update_hdr_sensitivity(view)

    view.switch_hdr.set_sensitive.assert_called_once_with(True)


def test_hdr_requires_wayland_or_gamescope_when_inactive(monkeypatch):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig()
    view = _make_view(config)
    monkeypatch.setattr(bottle_preferences.VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        bottle_preferences.DisplayUtils, "display_server_type", lambda: "wayland"
    )
    monkeypatch.setattr(bottle_preferences, "gamescope_available", "gamescope")

    PreferencesView._PreferencesView__update_hdr_sensitivity(view)
    view.switch_hdr.set_sensitive.assert_called_with(False)

    config.Parameters.wayland = True
    PreferencesView._PreferencesView__update_hdr_sensitivity(view)
    view.switch_hdr.set_sensitive.assert_called_with(True)

    config.Parameters.wayland = False
    config.Parameters.gamescope = True
    PreferencesView._PreferencesView__update_hdr_sensitivity(view)
    view.switch_hdr.set_sensitive.assert_called_with(True)


def test_gamescope_toggle_refreshes_hdr_sensitivity():
    from bottles.frontend.views.bottle_preferences import PreferencesView

    view = SimpleNamespace()
    view._PreferencesView__toggle_feature = Mock()
    view._PreferencesView__update_hdr_sensitivity = Mock()

    PreferencesView._PreferencesView__toggle_gamescope(view, None, True)

    view._PreferencesView__toggle_feature.assert_called_once_with(
        state=True, key="gamescope"
    )
    view._PreferencesView__update_hdr_sensitivity.assert_called_once_with()


@pytest.mark.parametrize(
    ("runner", "supported"),
    [
        ("soda-11.0-4", False),
        ("soda-11.0-5", True),
        ("soda-12.0-1", True),
        ("protosoda-11.0-1", False),
        ("wine-ge-8-26", False),
    ],
)
def test_adaptive_launch_requires_soda(runner, supported):
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig(Runner=runner)
    view = SimpleNamespace(
        config=config,
        switch_adaptive_launch=Mock(),
        row_adaptive_launch=Mock(),
        _adaptive_launch_warning=Mock(),
    )

    PreferencesView._PreferencesView__update_adaptive_launch_support(view)

    view.switch_adaptive_launch.set_sensitive.assert_called_once_with(supported)
    message = (
        ""
        if supported
        else "Soda 11.0-5 or newer is required to enable Adaptive Launch."
    )
    view.switch_adaptive_launch.set_tooltip_text.assert_called_once_with(message)
    view.row_adaptive_launch.set_tooltip_text.assert_called_once_with(message)
    view._adaptive_launch_warning.set_visible.assert_called_once_with(not supported)
