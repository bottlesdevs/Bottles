# ruff: noqa: E402

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango

from bottles.frontend.utils.gtk import GtkUtils


def test_full_width_string_list_factory_uses_unellipsized_labels():
    factory = GtkUtils.create_full_width_string_list_factory()
    list_item = Gtk.ListItem()

    factory.emit("setup", list_item)

    label = list_item.get_child()
    assert isinstance(label, Gtk.Label)
    assert label.get_ellipsize() == Pango.EllipsizeMode.NONE
    assert label.get_wrap() is False
    assert label.get_xalign() == 0
