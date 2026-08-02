# ruff: noqa: E402
from types import SimpleNamespace

from gi.repository import Gio

from bottles.frontend.utils.autostart import set_autostart_enabled

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.windows import launchoptions


class FakePortal:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.request = None

    def request_background(self, *args):
        self.request = args
        args[-2](self, object(), args[-1])

    def request_background_finish(self, _result):
        return self.accepted


def test_portal_autostart_uses_cli_dispatcher():
    portal = FakePortal()
    results = []

    set_autostart_enabled(
        None,
        True,
        results.append,
        portal=portal,
        sandboxed=True,
    )

    assert portal.request[2] == ["bottles-cli", "autostart"]
    assert int(portal.request[3]) == 1
    assert results == [True]


def test_portal_rejection_prevents_enabling_autostart():
    portal = FakePortal(accepted=False)
    results = []

    set_autostart_enabled(
        None,
        True,
        results.append,
        portal=portal,
        sandboxed=True,
    )

    assert results == [False]


def test_portal_rejection_still_allows_disabling_autostart():
    portal = FakePortal(accepted=False)
    results = []

    set_autostart_enabled(
        None,
        False,
        results.append,
        portal=portal,
        sandboxed=True,
    )

    assert int(portal.request[3]) == 0
    assert results == [True]


class FakeButton:
    def __init__(self):
        self.sensitive = True

    def get_sensitive(self):
        return self.sensitive

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


def test_first_autostart_program_requests_portal_before_save(monkeypatch):
    requests = []
    saved = []
    current = {"id": "service", "autostart": False}
    dialog = SimpleNamespace(
        btn_save=FakeButton(),
        program=current,
        config=SimpleNamespace(Name="Services"),
        manager=SimpleNamespace(
            local_bottles={
                "Services": SimpleNamespace(
                    Name="Services",
                    External_Programs={"service": current},
                )
            }
        ),
        switch_autostart=SimpleNamespace(get_active=lambda: True),
        window=SimpleNamespace(show_toast=lambda message: None),
    )
    setattr(dialog, "_LaunchOptionsDialog__idle_save", lambda: saved.append(True))

    def request(_parent, enabled, callback):
        requests.append(enabled)
        callback(True)

    monkeypatch.setattr(launchoptions, "set_autostart_enabled", request)
    monkeypatch.setattr(launchoptions.GLib, "idle_add", lambda callback: callback())

    launchoptions.LaunchOptionsDialog._LaunchOptionsDialog__save(dialog)

    assert requests == [True]
    assert saved == [True]


def test_additional_autostart_program_does_not_request_portal(monkeypatch):
    requests = []
    saved = []
    current = {"id": "service", "autostart": False}
    other = {"id": "tray", "autostart": True}
    dialog = SimpleNamespace(
        btn_save=FakeButton(),
        program=current,
        config=SimpleNamespace(Name="Services"),
        manager=SimpleNamespace(
            local_bottles={
                "Services": SimpleNamespace(
                    Name="Services",
                    External_Programs={"service": current, "tray": other},
                )
            }
        ),
        switch_autostart=SimpleNamespace(get_active=lambda: True),
        window=SimpleNamespace(show_toast=lambda message: None),
    )
    setattr(dialog, "_LaunchOptionsDialog__idle_save", lambda: saved.append(True))
    monkeypatch.setattr(
        launchoptions,
        "set_autostart_enabled",
        lambda *_args: requests.append(True),
    )
    monkeypatch.setattr(launchoptions.GLib, "idle_add", lambda callback: callback())

    launchoptions.LaunchOptionsDialog._LaunchOptionsDialog__save(dialog)

    assert requests == []
    assert saved == [True]


def test_last_autostart_program_disables_portal_before_save(monkeypatch):
    requests = []
    current = {"id": "service", "autostart": True}
    dialog = SimpleNamespace(
        btn_save=FakeButton(),
        program=current,
        config=SimpleNamespace(Name="Services"),
        manager=SimpleNamespace(
            local_bottles={
                "Services": SimpleNamespace(
                    Name="Services",
                    External_Programs={"service": current},
                )
            }
        ),
        switch_autostart=SimpleNamespace(get_active=lambda: False),
        window=SimpleNamespace(show_toast=lambda message: None),
    )
    setattr(dialog, "_LaunchOptionsDialog__idle_save", lambda: None)

    def request(_parent, enabled, callback):
        requests.append(enabled)
        callback(True)

    monkeypatch.setattr(launchoptions, "set_autostart_enabled", request)
    monkeypatch.setattr(launchoptions.GLib, "idle_add", lambda callback: callback())

    launchoptions.LaunchOptionsDialog._LaunchOptionsDialog__save(dialog)

    assert requests == [False]
