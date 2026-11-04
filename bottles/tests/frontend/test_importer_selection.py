# ruff: noqa: E402
from types import SimpleNamespace
import pytest

from gi.repository import Gio, GLib

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views import importer
from bottles.frontend.widgets import importer as importer_widget
from bottles.backend.models.result import Result


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


@pytest.mark.parametrize("success", (True, False, None))
def test_import_result_keeps_failed_prefix_available(monkeypatch, success):
    message = "This 32-bit prefix needs a runner with 32-bit Unix support."
    result = None if success is None else Result(success, message=message)
    toasts = []
    parent = SimpleNamespace(
        window=SimpleNamespace(show_toast=toasts.append),
        import_manager=SimpleNamespace(import_wineprefix=lambda **_kwargs: result),
    )
    monkeypatch.setattr(
        importer_widget, "RunAsync",
        lambda task, callback, **kwargs: callback(task(**kwargs)),
    )
    entry = importer_widget.ImporterEntry(
        parent, {"Name": "Prefix", "Manager": "Manual", "Lock": False}
    )

    entry.btn_import.emit("clicked")
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)

    assert entry.get_sensitive()
    assert entry.btn_import.get_visible() is not bool(success)
    assert entry.img_lock.get_visible() is bool(success)
    assert len(toasts) == 1
    if success is False:
        assert toasts == [message]
