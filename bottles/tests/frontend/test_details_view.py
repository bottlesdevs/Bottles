# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.frontend.views.details import DetailsView


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
