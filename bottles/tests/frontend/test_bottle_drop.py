from types import SimpleNamespace

import pytest
from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views import bottle_details  # noqa: E402


@pytest.mark.parametrize("name, accepted", [
    ("setup.EXE", True),
    ("setup.mSi", True),
    ("setup.exe", True),
    ("setup.exe.backup", False),
    ("setup.msi.txt", False),
])
def test_drop_checks_executable_suffix_without_case_sensitivity(monkeypatch, name, accepted):
    launches = []
    messages = []
    monkeypatch.setattr(
        bottle_details, "guard_sandbox_launch",
        lambda window, config, path, proceed: launches.append(path),
    )
    view = SimpleNamespace(
        drop_overlay=SimpleNamespace(set_visible=lambda _visible: None),
        window=SimpleNamespace(show_toast=messages.append),
        config=object(),
    )
    file = Gio.File.new_for_path("/owned/" + name)
    value = SimpleNamespace(get_files=lambda: [file])

    result = bottle_details.BottleView.on_drop(view, None, value, 0, 0)

    assert bool(launches) is accepted
    assert bool(messages) is not accepted
    assert result is accepted
