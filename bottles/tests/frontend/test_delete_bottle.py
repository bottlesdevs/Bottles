# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.config import BottleConfig
from bottles.frontend.views import bottle_details
from bottles.frontend.views.bottle_details import BottleView


class FakeDialog:
    def __init__(self, events):
        self.events = events
        self.response = None

    def add_response(self, *_args):
        pass

    def set_response_appearance(self, *_args):
        pass

    def connect(self, _signal, callback):
        self.response = callback

    def present(self):
        pass

    def destroy(self):
        self.events.append("destroy")


@pytest.fixture
def harness(monkeypatch):
    events = []
    callbacks = []
    dialog = FakeDialog(events)

    monkeypatch.setattr(
        bottle_details,
        "Adw",
        SimpleNamespace(
            MessageDialog=SimpleNamespace(new=lambda *_args: dialog),
            ResponseAppearance=SimpleNamespace(DESTRUCTIVE=object()),
        ),
    )
    def run_async(*_args, **kwargs):
        events.append("delete")
        callbacks.append(kwargs["callback"])

    monkeypatch.setattr(bottle_details, "RunAsync", run_async)
    monkeypatch.setattr(
        bottle_details.GLib,
        "idle_add",
        lambda callback, *_args: events.append("idle") or callback(),
    )

    view = SimpleNamespace(
        config=BottleConfig(Name="Bottle"),
        manager=SimpleNamespace(delete_bottle=lambda **_kwargs: None),
        window=SimpleNamespace(
            page_list=SimpleNamespace(
                disable_bottle=lambda _config: events.append("navigate"),
                update_bottles_list=lambda: events.append("refresh"),
            )
        ),
    )
    return view, dialog, events, callbacks


def test_delete_closes_the_dialog_before_leaving_the_page(harness):
    view, dialog, events, _callbacks = harness

    BottleView._BottleView__confirm_delete(view, None)
    dialog.response(dialog, "ok")

    assert events[0] == "destroy"
    assert events.index("destroy") < events.index("navigate")
    assert "delete" in events


def test_cancelling_delete_only_closes_the_dialog(harness):
    view, dialog, events, callbacks = harness

    BottleView._BottleView__confirm_delete(view, None)
    dialog.response(dialog, "cancel")

    assert events == ["destroy"]
    assert callbacks == []


def test_delete_refreshes_list_from_async_callback(harness):
    view, dialog, events, callbacks = harness

    BottleView._BottleView__confirm_delete(view, None)
    dialog.response(dialog, "ok")
    assert "refresh" not in events

    callbacks[0](True, None)

    assert events[-1] == "refresh"
