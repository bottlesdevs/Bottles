# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.config import BottleConfig
from bottles.frontend.views.details import DetailsView
from bottles.frontend.views.eagle import EagleView


def _make_view(transition_running, showing_details):
    unloaded = []
    view = SimpleNamespace(unload_view=lambda *_args: unloaded.append(True))
    other_page = object()
    view.window = SimpleNamespace(
        main_leaf=SimpleNamespace(
            get_child_transition_running=lambda: transition_running,
            get_visible_child=lambda: view if showing_details else other_page,
        )
    )
    return view, unloaded


@pytest.mark.parametrize(
    ("transition_running", "showing_details", "expects_unload"),
    (
        (False, False, True),
        (False, True, False),
        (True, False, False),
        (True, True, False),
    ),
)
def test_views_survive_until_the_leaflet_settles_elsewhere(
    transition_running, showing_details, expects_unload
):
    view, unloaded = _make_view(transition_running, showing_details)

    DetailsView._DetailsView__on_main_leaf_changed(view)

    assert bool(unloaded) is expects_unload


def test_unload_view_empties_the_page_stack():
    from gi.repository import Adw, Gtk

    stack = Gtk.Stack()
    stack.add_named(Adw.Bin(), "preferences")
    stack.add_named(Adw.Bin(), "dependencies")
    view = SimpleNamespace(stack_bottle=stack)

    DetailsView.unload_view(view)

    assert stack.get_first_child() is None


def test_eagle_follows_the_selected_bottle():
    eagle = EagleView(SimpleNamespace(), BottleConfig())
    previous_manager = eagle.manager
    unused = SimpleNamespace(set_config=lambda **kwargs: None, update=lambda **kwargs: None)
    view = SimpleNamespace(
        view_bottle=unused,
        view_preferences=unused,
        view_taskmanager=unused,
        view_installers=unused,
        view_registry_rules=unused,
        view_versioning=unused,
        view_eagle=eagle,
    )
    for config in (
        BottleConfig(Name="First", Runner="soda-11.0-34"),
        BottleConfig(Name="Second", Environment="Steam", RunnerPath="/runner"),
    ):
        DetailsView.set_config(view, config, rebuild_pages=False)
        assert eagle.config is config
        assert eagle.manager.config is config
        assert eagle.manager is not previous_manager
        previous_manager = eagle.manager
