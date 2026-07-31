from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import Gio

from bottles.backend.models.config import BottleConfig
from bottles.backend.wine import winecommand
from bottles.backend.wine.winecommand import WineCommand

resource_path = Path("/app/share/bottles/bottles.gresource")
if not resource_path.exists():
    pytest.skip(
        "Gamescope frontend tests require the Bottles Flatpak runtime",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))


def _make_dialog(callback):
    return SimpleNamespace(
        toggle_borderless=Mock(),
        toggle_fullscreen=Mock(),
        _GamescopeDialog__change_wtype=callback,
    )


@pytest.mark.parametrize("wtype", ["b", "f"])
def test_window_type_can_be_disabled(wtype):
    from bottles.frontend.windows.gamescope import GamescopeDialog

    widget = Mock()
    widget.get_active.return_value = False
    dialog = _make_dialog(GamescopeDialog._GamescopeDialog__change_wtype)

    GamescopeDialog._GamescopeDialog__change_wtype(dialog, widget, wtype)

    dialog.toggle_borderless.set_active.assert_not_called()
    dialog.toggle_fullscreen.set_active.assert_not_called()


@pytest.mark.parametrize(
    ("wtype", "active_toggle", "inactive_toggle"),
    [
        ("b", "toggle_borderless", "toggle_fullscreen"),
        ("f", "toggle_fullscreen", "toggle_borderless"),
    ],
)
def test_window_types_remain_exclusive(wtype, active_toggle, inactive_toggle):
    from bottles.frontend.windows.gamescope import GamescopeDialog

    widget = Mock()
    widget.get_active.return_value = True
    dialog = _make_dialog(GamescopeDialog._GamescopeDialog__change_wtype)

    GamescopeDialog._GamescopeDialog__change_wtype(dialog, widget, wtype)

    getattr(dialog, active_toggle).set_active.assert_called_once_with(True)
    getattr(dialog, inactive_toggle).set_active.assert_called_once_with(False)


def test_disabled_window_types_are_saved():
    from bottles.frontend.windows.gamescope import GamescopeDialog

    value_widget = Mock(**{"get_value.return_value": 0})
    state_widget = Mock(**{"get_state.return_value": False})
    inactive_toggle = Mock(**{"get_active.return_value": False})
    text_widget = Mock(**{"get_text.return_value": ""})
    dialog = SimpleNamespace(
        spin_width=value_widget,
        spin_height=value_widget,
        spin_gamescope_width=value_widget,
        spin_gamescope_height=value_widget,
        switch_fsr=state_widget,
        spin_sharpening_strength=value_widget,
        spin_fps_limit=value_widget,
        spin_fps_limit_no_focus=value_widget,
        switch_scaling=inactive_toggle,
        toggle_borderless=inactive_toggle,
        toggle_fullscreen=inactive_toggle,
        entry_custom_options=text_widget,
        manager=Mock(),
        config=object(),
        destroy=Mock(),
    )

    GamescopeDialog._GamescopeDialog__idle_save(dialog)

    settings = {
        call.kwargs["key"]: call.kwargs["value"]
        for call in dialog.manager.update_config.call_args_list
    }
    assert settings["gamescope_borderless"] is False
    assert settings["gamescope_fullscreen"] is False


def test_windowed_gamescope_command_has_no_window_type_flags(monkeypatch):
    config = BottleConfig()
    config.Parameters.gamescope_borderless = False
    config.Parameters.gamescope_fullscreen = False
    command = SimpleNamespace(config=config, gamescope_activated=True)
    monkeypatch.setattr(winecommand, "gamescope_available", "gamescope")

    assert WineCommand._get_gamescope_cmd(command) == "gamescope"
