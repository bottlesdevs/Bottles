# ruff: noqa: E402
from types import SimpleNamespace

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views import importer


def test_selected_folder_is_forwarded_to_prefix_search():
    searches = []
    view = SimpleNamespace(
        btn_select_prefixes=object(),
    )
    setattr(
        view,
        "_ImporterView__search_prefixes",
        lambda widget, paths: searches.append((widget, paths)),
    )
    dialog = SimpleNamespace(
        select_folder_finish=lambda _result: Gio.File.new_for_path(
            "/tmp/PlayOnLinux prefixes"
        )
    )

    importer.ImporterView._ImporterView__folder_selected(view, dialog, object())

    assert searches == [
        (view.btn_select_prefixes, ["/tmp/PlayOnLinux prefixes"]),
    ]
