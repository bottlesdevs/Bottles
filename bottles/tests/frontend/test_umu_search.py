# ruff: noqa: E402
import io
import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.backend.umu.database import UmuDatabaseClient
from bottles.frontend.windows import umu


def test_database_failure_can_be_retried_without_a_crash_report(monkeypatch, tmp_path):
    available = False

    def opener(_request, timeout):
        if not available:
            raise urllib.error.URLError("offline")
        return io.BytesIO(json.dumps([{
            "title": "Example", "store": "gog", "codename": "example",
            "umu_id": "umu-example", "acronym": "example",
        }]).encode())

    view = SimpleNamespace(
        database=UmuDatabaseClient(tmp_path / "database.json", opener=opener),
        entry_search=Mock(), stack_results=Mock(), spinner=Mock(), group_results=Mock(),
        _UmuSearchDialog__search=Mock(),
    )
    monkeypatch.setattr(
        umu, "RunAsync",
        lambda task_func, callback, **kwargs: callback(task_func(**kwargs)),
    )

    umu.UmuSearchDialog._UmuSearchDialog__load(view)

    view.spinner.stop.assert_called_once()
    view.stack_results.set_visible_child_name.assert_called_with("error")
    view.entry_search.set_sensitive.assert_called_with(False)
    view._UmuSearchDialog__search.assert_not_called()

    available = True
    umu.UmuSearchDialog._UmuSearchDialog__load(view, refresh=True)

    view.entry_search.set_sensitive.assert_called_with(True)
    view._UmuSearchDialog__search.assert_called_once()
    assert (tmp_path / "database.json").is_file()
