# ruff: noqa: E402

from types import SimpleNamespace

from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.config import BottleConfig
from bottles.frontend.views import bottle_details
from bottles.frontend.views.bottle_details import BottleView


class WidgetStub:
    def set_text(self, _text):
        pass

    def set_tooltip_text(self, _text):
        pass

    def set_visible(self, _visible):
        pass


def test_missing_runner_dialog_waits_for_versioning_upgrade(monkeypatch):
    events = []
    callbacks = []
    widget = WidgetStub()
    config = BottleConfig(
        Name="Test",
        Runner="missing-runner",
        Environment="Gaming",
        Update_Date="2026-01-01 00:00:00.000000",
        Versioning=True,
    )

    def show_upgrade(on_close=None):
        events.append("upgrade")
        callbacks.append(on_close)

    view = SimpleNamespace(
        manager=SimpleNamespace(
            runners_available=[],
            versioning_manager=SimpleNamespace(needs_migration=lambda _config: True),
        ),
        label_name=widget,
        label_arch=widget,
        label_runner=widget,
        label_environment=widget,
        dot_versioning=widget,
        btn_versioning_badge=widget,
        label_state=widget,
        _BottleView__update_by_env=lambda: None,
        _BottleView__set_steam_rules=lambda: None,
        _BottleView__upgrade_versioning=show_upgrade,
        _BottleView__alert_missing_runner=lambda: events.append("missing-runner"),
        update_programs=lambda: None,
        populate_updates=lambda: None,
    )

    monkeypatch.setattr(
        bottle_details.ManagerUtils,
        "get_bottle_path",
        lambda _config: "/tmp/test-bottle",
    )
    monkeypatch.setattr(bottle_details.os.path, "exists", lambda _path: False)

    BottleView.set_config(view, config)

    assert events == ["upgrade"]
    assert callbacks[0] is not None

    callbacks[0]()

    assert events == ["upgrade", "missing-runner"]


def test_versioning_upgrade_schedules_follow_up_after_close(monkeypatch):
    events = []
    connections = []

    class DialogStub:
        def connect(self, signal, callback):
            events.append("connect")
            connections.append((signal, callback))

        def present(self):
            events.append("present")

    dialog = DialogStub()
    monkeypatch.setattr(
        bottle_details,
        "UpgradeVersioningDialog",
        lambda _parent: dialog,
    )
    monkeypatch.setattr(
        bottle_details.GLib,
        "idle_add",
        lambda callback: events.append("scheduled") or callback(),
    )

    BottleView._BottleView__upgrade_versioning(
        SimpleNamespace(),
        lambda: events.append("missing-runner"),
    )

    assert events == ["connect", "present"]
    assert connections[0][0] == "close-request"

    assert connections[0][1](dialog) is False
    assert events == ["connect", "present", "scheduled", "missing-runner"]
