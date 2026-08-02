from threading import Event

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager


@pytest.mark.parametrize("sandbox", [False, True])
def test_create_bottle_applies_sandbox_before_wineboot(monkeypatch, tmp_path, sandbox):
    captured = {}
    cancel_event = Event()

    class WineBoot:
        def __init__(self, config):
            captured["config"] = config

        def init(self):
            users = tmp_path / "Sandboxed" / "drive_c" / "users"
            captured["user_dir"] = (users / "hostuser").is_dir()
            captured["steamuser"] = str((users / "steamuser").readlink())
            cancel_event.set()

    manager = object.__new__(Manager)
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(
        manager_module.FileUtils, "wait_for_files", lambda *_args, **_kwargs: False
    )
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: None,
    )
    monkeypatch.setattr(manager_module, "Reg", lambda _config: object())
    monkeypatch.setattr(manager_module, "RegKeys", lambda _config: object())
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)
    monkeypatch.setattr(manager_module, "WineServer", lambda _config: object())
    monkeypatch.setenv("USER", "hostuser")

    result = Manager.create_bottle(
        manager,
        name="Sandboxed",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
        sandbox=sandbox,
        cancel_event=cancel_event,
    )

    assert result.ok is False
    assert captured["config"].Parameters.sandbox is sandbox
    assert "XMODIFIERS" in captured["config"].Inherited_Environment_Variables
    assert captured["user_dir"] is True
    assert captured["steamuser"] == "hostuser"


def test_shared_user_profile_survives_home_link_cleanup(monkeypatch, tmp_path):
    cancel_event = Event()
    wait_calls = 0

    class WineBoot:
        def __init__(self, _config):
            pass

        def init(self):
            users = tmp_path / "Shared" / "drive_c" / "users"
            host_documents = tmp_path / "host-documents"
            host_documents.mkdir()
            (users / "hostuser" / "Documents").symlink_to(host_documents)

    def wait_for_files(*_args, **_kwargs):
        nonlocal wait_calls
        wait_calls += 1
        if wait_calls == 2:
            cancel_event.set()
        return True

    manager = object.__new__(Manager)
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    monkeypatch.setenv("USER", "hostuser")
    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(manager_module.FileUtils, "wait_for_files", wait_for_files)
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: None,
    )
    monkeypatch.setattr(manager_module, "Reg", lambda _config: object())
    monkeypatch.setattr(manager_module, "RegKeys", lambda _config: object())
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)
    monkeypatch.setattr(manager_module, "WineServer", lambda _config: object())

    result = Manager.create_bottle(
        manager,
        name="Shared",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
        cancel_event=cancel_event,
    )

    users = tmp_path / "Shared" / "drive_c" / "users"
    assert result.ok is False
    assert (users / "steamuser").is_symlink()
    assert str((users / "steamuser").readlink()) == "hostuser"
    assert (users / "hostuser" / "Documents").is_dir()
    assert not (users / "hostuser" / "Documents").is_symlink()


def test_create_bottle_rejects_profile_link_outside_prefix(monkeypatch, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_link = outside / "Documents"
    outside_link.symlink_to(tmp_path)
    wineboot_created = False

    class WineBoot:
        def __init__(self, _config):
            nonlocal wineboot_created
            wineboot_created = True

    def unpack_template(_template, _config):
        users = tmp_path / "Unsafe" / "drive_c" / "users"
        users.mkdir()
        (users / "steamuser").symlink_to(outside)
        return True

    manager = object.__new__(Manager)
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    monkeypatch.setenv("USER", "hostuser")
    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: {
            "config": {"Installed_Dependencies": [], "Uninstallers": []}
        },
    )
    monkeypatch.setattr(
        manager_module.TemplateManager, "unpack_template", unpack_template
    )
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)

    result = Manager.create_bottle(
        manager,
        name="Unsafe",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
    )

    assert result.ok is False
    assert result.message == "Failed to prepare the bottle user profile."
    assert wineboot_created is False
    assert outside_link.is_symlink()
