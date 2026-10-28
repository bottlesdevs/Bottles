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


@pytest.mark.parametrize("nvidia", (True, False))
@pytest.mark.parametrize("enabled", (True, False))
def test_nvapi_remains_manageable_after_gpu_change(monkeypatch, nvidia, enabled):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig()
    config.Parameters.dxvk_nvapi = enabled
    view = SimpleNamespace(config=config, row_nvapi=Mock(), combo_nvapi=Mock())
    monkeypatch.setattr(bottle_preferences.GPUUtils, "is_gpu", lambda *_args: nvidia)

    PreferencesView._PreferencesView__update_nvapi_visibility(view)

    view.row_nvapi.set_visible.assert_called_once_with(nvidia or enabled)
    view.combo_nvapi.set_visible.assert_called_once_with(nvidia or enabled)


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


def test_unchanged_sync_does_not_update_bottle(monkeypatch):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig()
    config.Parameters.sync = "ntsync"
    view = SimpleNamespace(
        config=config,
        combo_sync=Mock(),
        manager=Mock(),
        queue=Mock(),
    )
    view.combo_sync.get_selected.return_value = 3
    run_async = Mock()
    monkeypatch.setattr(bottle_preferences, "RunAsync", run_async)

    PreferencesView._PreferencesView__set_sync_type(view)

    run_async.assert_not_called()
    view.manager.update_config.assert_not_called()
    view.combo_sync.set_sensitive.assert_not_called()
    view.queue.add_task.assert_not_called()


@pytest.mark.parametrize("error", (None, ValueError("winecfg failed")))
def test_windows_version_is_saved_only_after_winecfg_succeeds(monkeypatch, error):
    from gi.repository import Adw, GLib, Gtk

    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    Adw.init()
    config = BottleConfig(Windows="win10")
    combo = Adw.ComboRow(model=Gtk.StringList.new(["Windows 10", "Windows 11"]))
    combo.set_selected(0)
    view = SimpleNamespace(
        config=config,
        combo_windows=combo,
        windows_versions={"win10": "Windows 10", "win11": "Windows 11"},
        manager=Mock(),
        queue=Mock(),
        spinner_windows=Mock(),
    )
    view._PreferencesView__set_windows = lambda *_args: (
        PreferencesView._PreferencesView__set_windows(view)
    )
    combo.connect("notify::selected", view._PreferencesView__set_windows)
    run_async = Mock()
    monkeypatch.setattr(bottle_preferences, "RunAsync", run_async)
    monkeypatch.setattr(bottle_preferences, "RegKeys", Mock())

    def persist(**kwargs):
        config.Windows = kwargs["value"]
        return SimpleNamespace(data={"config": config})

    view.manager.update_config.side_effect = persist
    combo.set_selected(1)

    assert config.Windows == "win10"
    view.manager.update_config.assert_not_called()
    assert not combo.get_sensitive()
    callback = run_async.call_args.kwargs["callback"]
    callback(None, error)
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)

    if error:
        assert config.Windows == "win10"
        assert combo.get_selected() == 0
        view.manager.update_config.assert_not_called()
    else:
        assert config.Windows == "win11"
        assert combo.get_selected() == 1
        view.manager.update_config.assert_called_once_with(
            config=config, key="Windows", value="win11"
        )
    assert run_async.call_count == 1
    assert combo.get_sensitive()
    view.queue.end_task.assert_called_once_with()
    view.spinner_windows.stop.assert_called_once_with()


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
        switch_eagle_tracing=Mock(),
        row_eagle_tracing=Mock(),
        _PreferencesView__toggle_feature_cb=Mock(),
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


def test_open_eagle_logs_keeps_window_alive_when_directory_is_unwritable(monkeypatch):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    def denied(*args, **kwargs):
        raise PermissionError("log directory is not writable")

    monkeypatch.setattr(
        bottle_preferences.ManagerUtils, "get_bottle_path", lambda _config: "/home/test/bottle"
    )
    monkeypatch.setattr(bottle_preferences.os, "makedirs", denied)
    opened = Mock()
    monkeypatch.setattr(bottle_preferences.ManagerUtils, "open_filemanager", opened)
    view = SimpleNamespace(config=Mock(), window=SimpleNamespace(show_toast=Mock()))
    PreferencesView._PreferencesView__open_eagle_logs(view, None)
    view.window.show_toast.assert_called_once()
    opened.assert_not_called()


def _make_graphics_view(config):
    from bottles.frontend.views.bottle_preferences import PreferencesView

    view = SimpleNamespace(
        config=config,
        manager=Mock(
            dxvk_available=["dxvk-old", "dxvk-new"],
            vkd3d_available=["vkd3d-old", "vkd3d-new"],
        ),
        combo_dxvk=Mock(),
        combo_vkd3d=Mock(),
        spinner_dxvk=Mock(),
        spinner_vkd3d=Mock(),
        queue=Mock(),
    )
    view._PreferencesView__set_dxvk = Mock()
    view._PreferencesView__set_vkd3d = Mock()
    view._PreferencesView__set_graphics_status = lambda *args: (
        PreferencesView._PreferencesView__set_graphics_status(view, *args)
    )
    view.set_dxvk_status = lambda **kwargs: (
        PreferencesView.set_dxvk_status.__wrapped__(view, **kwargs)
    )
    view.set_vkd3d_status = lambda **kwargs: (
        PreferencesView.set_vkd3d_status.__wrapped__(view, **kwargs)
    )
    return view


@pytest.mark.parametrize("component", ["dxvk", "vkd3d"])
def test_graphics_removal_does_not_save_while_pending(monkeypatch, component):
    from bottles.frontend.views import bottle_preferences
    from bottles.frontend.views.bottle_preferences import PreferencesView

    config = BottleConfig(DXVK="dxvk-old", VKD3D="vkd3d-old")
    setattr(config.Parameters, component, True)
    view = _make_graphics_view(config)
    getattr(view, f"combo_{component}").get_selected.return_value = 0
    jobs = []
    monkeypatch.setattr(
        bottle_preferences, "RunAsync", lambda **kwargs: jobs.append(kwargs)
    )

    getattr(PreferencesView, f"_PreferencesView__set_{component}")(view)

    assert getattr(config.Parameters, component)
    view.manager.update_config.assert_not_called()
    view.combo_dxvk.set_sensitive.assert_called_once_with(False)
    view.combo_vkd3d.set_sensitive.assert_called_once_with(False)
    assert len(jobs) == 1 and jobs[0]["enabled"] is False


@pytest.mark.parametrize("component", ["dxvk", "vkd3d"])
def test_graphics_failure_restores_selector(component):
    from bottles.backend.models.result import Result

    config = BottleConfig(DXVK="dxvk-old", VKD3D="vkd3d-old")
    setattr(config.Parameters, component, True)
    view = _make_graphics_view(config)

    getattr(view, f"set_{component}_status")(status=Result(False, message="failed"))

    getattr(view, f"combo_{component}").set_selected.assert_called_once_with(1)
    getattr(view, f"combo_{component}").handler_block_by_func.assert_called_once()
    getattr(view, f"combo_{component}").handler_unblock_by_func.assert_called_once()
    assert getattr(config.Parameters, component)
    view.queue.end_task.assert_called_once()


def test_graphics_success_updates_both_selectors():
    from bottles.backend.models.result import Result

    view = _make_graphics_view(BottleConfig())
    updated = BottleConfig(DXVK="dxvk-new", VKD3D="vkd3d-new")
    updated.Parameters.dxvk = True
    updated.Parameters.vkd3d = True

    view.set_vkd3d_status(status=Result(True, data={"config": updated}))

    assert view.config is updated
    view.combo_dxvk.set_selected.assert_called_once_with(2)
    view.combo_vkd3d.set_selected.assert_called_once_with(2)
    view.queue.end_task.assert_called_once()
