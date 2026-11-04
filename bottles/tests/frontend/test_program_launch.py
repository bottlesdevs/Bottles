from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bottles.frontend.utils import program


@pytest.mark.parametrize("exists,pre_script,launch", [
    (False, None, False), (False, "mount-drive.sh", True),
    (True, None, True), (None, None, True),
])
def test_missing_program_warning_keeps_the_shortcut(monkeypatch, exists, pre_script, launch):
    item = {"path": "/external/Game.exe", "pre_script": pre_script}
    window = SimpleNamespace(show_toast=Mock())
    ready, checked = Mock(), Mock()
    monkeypatch.setattr(program.ManagerUtils, "program_exists", lambda **_kwargs: exists)
    monkeypatch.setattr(program, "RunAsync", lambda task, callback, **kwargs: callback(task(**kwargs)))

    program.guard_program_launch(window, object(), item, ready, checked)

    assert ready.called is launch
    assert window.show_toast.called is (exists is False)
    checked.assert_called_once_with(exists)
    assert item == {"path": "/external/Game.exe", "pre_script": pre_script}
