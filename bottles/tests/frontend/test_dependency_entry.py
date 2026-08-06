# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.config import BottleConfig
from bottles.frontend.widgets.dependency import DependencyEntry

MANIFEST = {
    "Description": "A dependency",
    "Category": "Fonts",
    "Arch": "win64_win32",
}


def _make_window(online, cache_calls):
    def is_dependency_cached(name, **kwargs):
        cache_calls.append(name)
        return False

    return SimpleNamespace(
        manager=SimpleNamespace(
            utils_conn=SimpleNamespace(status=online),
            dependency_manager=SimpleNamespace(
                is_dependency_cached=is_dependency_cached
            ),
        ),
        page_details=SimpleNamespace(queue=None),
    )


def test_installed_dependency_row_shows_its_name():
    window = _make_window(online=True, cache_calls=[])
    config = BottleConfig(Name="Bottle", Installed_Dependencies=["arial32"])

    entry = DependencyEntry(
        window=window,
        config=config,
        dependency=("arial32", MANIFEST),
        plain=True,
    )

    assert entry.get_title() == "arial32"


@pytest.mark.parametrize(
    ("online", "expects_lookup"),
    ((True, False), (False, True)),
)
def test_cache_lookup_only_runs_offline(online, expects_lookup):
    cache_calls = []
    window = _make_window(online=online, cache_calls=cache_calls)
    config = BottleConfig(Name="Bottle", Installed_Dependencies=["arial32"])

    DependencyEntry(
        window=window,
        config=config,
        dependency=("d3dx9", MANIFEST),
    )

    assert bool(cache_calls) is expects_lookup


def test_cache_lookup_is_skipped_without_installed_dependencies():
    cache_calls = []
    window = _make_window(online=False, cache_calls=cache_calls)
    config = BottleConfig(Name="Bottle", Installed_Dependencies=[])

    DependencyEntry(
        window=window,
        config=config,
        dependency=("d3dx9", MANIFEST),
    )

    assert cache_calls == []
