# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Gio

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "Library frontend tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend.views import library as library_module
from bottles.frontend.views.library import LibraryView, _ordered_library_entries


def test_library_entries_are_ordered_by_name():
    entries = {
        "third": {"name": "Zulu"},
        "first": {"name": "alpha"},
        "second": {"name": "Bravo"},
    }

    ordered = _ordered_library_entries(entries)

    assert [entry_uuid for entry_uuid, _entry in ordered] == [
        "first",
        "second",
        "third",
    ]


def test_delete_entry_refreshes_library(monkeypatch):
    removed = []
    updates = []
    manager = SimpleNamespace(
        remove_from_library=lambda entry_uuid, config: removed.append(
            (entry_uuid, config)
        )
    )
    monkeypatch.setattr(library_module, "LibraryManager", lambda: manager)
    view = SimpleNamespace(update=lambda: updates.append(True))
    entry = SimpleNamespace(uuid="entry-id", config="config")

    LibraryView._LibraryView__delete_entry(view, entry)

    assert removed == [("entry-id", "config")]
    assert updates == [True]
