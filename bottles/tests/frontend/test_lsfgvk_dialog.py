import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gi.repository import Gio

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "lsfg-vk frontend tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.backend.utils.lsfgvk import (  # noqa: E402
    remove_lsfg_vk_dll,
    store_lsfg_vk_dll,
)
from bottles.frontend.windows.lsfgvk import LsfgVkDialog  # noqa: E402


def _dialog(dll_path):
    return SimpleNamespace(
        dll_path=dll_path,
        spin_multiplier=Mock(**{"get_value.return_value": 3}),
        spin_flow_scale=Mock(**{"get_value.return_value": 0.7}),
        switch_performance_mode=Mock(**{"get_active.return_value": True}),
        manager=Mock(),
        config=object(),
        window=SimpleNamespace(show_toast=Mock()),
        close=Mock(),
    )


def test_lsfg_vk_dialog_saves_settings(tmp_path):
    dll = tmp_path / "Lossless.dll"
    dll.touch()
    dialog = _dialog(str(dll))

    LsfgVkDialog._LsfgVkDialog__idle_save(dialog)

    settings = {
        call.kwargs["key"]: call.kwargs["value"]
        for call in dialog.manager.update_config.call_args_list
    }
    assert settings == {
        "lsfg_vk_multiplier": 3,
        "lsfg_vk_flow_scale": 0.7,
        "lsfg_vk_performance_mode": True,
    }
    dialog.close.assert_called_once_with()


def test_lsfg_vk_dialog_rejects_a_missing_dll(tmp_path):
    dialog = _dialog(str(tmp_path / "Lossless.dll"))

    LsfgVkDialog._LsfgVkDialog__idle_save(dialog)

    dialog.manager.update_config.assert_not_called()
    dialog.window.show_toast.assert_called_once()
    dialog.close.assert_not_called()


def test_lsfg_vk_dll_is_copied_inside_the_bottle(tmp_path):
    source_dir = tmp_path / "Steam" / "Lossless Scaling"
    source_dir.mkdir(parents=True)
    source = source_dir / "Lossless.dll"
    source.write_bytes(b"MZnew payload")
    bottle = tmp_path / "Bottle"
    old_target = bottle / "lsfg-vk" / "Lossless.dll"
    old_target.parent.mkdir(parents=True)
    old_target.write_bytes(b"MZold payload")

    target = store_lsfg_vk_dll(str(source), str(bottle))

    assert target == str(old_target)
    assert old_target.read_bytes() == b"MZnew payload"
    assert not list(old_target.parent.glob(".Lossless-*.dll"))


def test_lsfg_vk_dll_can_be_removed(tmp_path):
    dll = tmp_path / "Bottle" / "lsfg-vk" / "Lossless.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"MZpayload")

    remove_lsfg_vk_dll(str(tmp_path / "Bottle"))

    assert not dll.exists()
    assert not dll.parent.exists()


@pytest.mark.parametrize(
    ("name", "contents"),
    [
        ("Other.dll", b"MZpayload"),
        ("Lossless.dll", b"not a PE file"),
    ],
)
def test_lsfg_vk_dll_copy_rejects_invalid_files(tmp_path, name, contents):
    source = tmp_path / name
    source.write_bytes(contents)
    bottle = tmp_path / "Bottle"

    with pytest.raises(ValueError):
        store_lsfg_vk_dll(str(source), str(bottle))

    assert not (bottle / "lsfg-vk" / "Lossless.dll").exists()
