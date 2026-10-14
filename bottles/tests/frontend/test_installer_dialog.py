from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bottles.backend.models.result import Result


class TemplateStub:
    def __init__(self, **_kwargs):
        pass

    def __call__(self, cls):
        return cls

    @staticmethod
    def Child():
        return None


def load_installer_dialog():
    import gi

    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    Gtk = import_module("gi.repository.Gtk")

    spec = spec_from_file_location(
        "_test_installer_module",
        Path(__file__).parents[2] / "frontend" / "windows" / "installer.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the installer module")
    installer_module = module_from_spec(spec)

    template = Gtk.Template
    Gtk.Template = TemplateStub
    try:
        spec.loader.exec_module(installer_module)
    finally:
        Gtk.Template = template
    return installer_module.InstallerDialog


InstallerDialog = load_installer_dialog()


def test_installer_progress_displays_percentage():
    dialog = SimpleNamespace(progressbar=Mock())

    InstallerDialog.update_progress.__wrapped__(dialog, 0.42)

    dialog.progressbar.set_fraction.assert_called_once_with(0.42)
    dialog.progressbar.set_text.assert_called_once_with("42%")
    dialog.progressbar.set_show_text.assert_called_once_with(True)


def test_installer_progress_restores_overall_progress():
    dialog = SimpleNamespace(
        progressbar=Mock(),
        _InstallerDialog__current_step=2,
        _InstallerDialog__steps=4,
    )

    InstallerDialog.update_progress.__wrapped__(dialog, None)

    dialog.progressbar.set_fraction.assert_called_once_with(0.5)
    dialog.progressbar.set_show_text.assert_called_once_with(False)


def test_installer_activity_displays_manifest_label():
    dialog = SimpleNamespace(label_activity=Mock())

    InstallerDialog.update_activity.__wrapped__(dialog, "Microsoft 365 setup")

    dialog.label_activity.set_label.assert_called_once_with(
        "Running Microsoft 365 setup..."
    )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (Result(False, message="Download failed."), "Download failed."),
        (Result(False, data={"message": "Setup failed."}), "Setup failed."),
        (Result(False), "Installer failed with unknown error"),
    ],
)
def test_installer_failure_callback_displays_error(monkeypatch, result, message):
    pending = []
    method = InstallerDialog._InstallerDialog__install
    monkeypatch.setitem(
        method.__globals__, "RunAsync", lambda **kwargs: pending.append(kwargs)
    )
    monkeypatch.setattr(
        method.__globals__["GLib"], "timeout_add_seconds", lambda *_args: 1
    )
    dialog = Mock()

    method(dialog)
    pending[0]["callback"].__wrapped__(result)

    dialog._InstallerDialog__error.assert_called_once_with(message)


def test_missing_manifest_stops_before_starting_installation():
    dialog = Mock(installer=("office",))
    dialog.manager.installer_manager.get_installer.return_value = False

    InstallerDialog._InstallerDialog__check_resources(dialog)

    dialog._InstallerDialog__error.assert_called_once_with(
        "Could not load the installer. Please try again."
    )
    dialog.manager.installer_manager.has_local_resources.assert_not_called()
    dialog._InstallerDialog__install.assert_not_called()
