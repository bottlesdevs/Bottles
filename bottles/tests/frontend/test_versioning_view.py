# ruff: noqa: E402

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GLib, Gtk

blueprint_compiler = shutil.which("blueprint-compiler")
resource_bundle = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if blueprint_compiler is None or not resource_bundle.is_file():
    pytest.skip("Bottles Flatpak test resources are required", allow_module_level=True)

resource_dir = tempfile.TemporaryDirectory(prefix="bottles-versioning-view-")
source_root = Path(__file__).resolve().parents[3]
subprocess.run(
    [
        blueprint_compiler,
        "compile",
        str(source_root / "bottles/frontend/ui/details-versioning.blp"),
        "--output",
        str(Path(resource_dir.name) / "details-versioning.ui"),
    ],
    check=True,
)
os.environ["G_RESOURCE_OVERLAYS"] = f"/com/usebottles/bottles={resource_dir.name}"

Gio.resources_register(Gio.Resource.load(str(resource_bundle)))

from bottles.backend.models.config import BottleConfig
from bottles.frontend.views.bottle_versioning import VersioningView


def test_empty_snapshot_page_is_visible():
    config = BottleConfig()
    config.Versioning = True
    details = SimpleNamespace(
        window=SimpleNamespace(
            manager=SimpleNamespace(versioning_manager=object()),
        ),
    )
    view = VersioningView(details, config)
    view.status_page.set_visible(True)
    view.pref_page.set_visible(False)
    window = Gtk.Window(child=view)
    window.set_default_size(640, 480)
    window.present()

    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)

    assert isinstance(view, Adw.Bin)
    assert view.status_page.get_mapped()
    assert view.status_page.get_width() > 0
    assert view.status_page.get_height() > 0
    window.destroy()
