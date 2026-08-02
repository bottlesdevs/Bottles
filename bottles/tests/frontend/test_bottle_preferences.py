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
