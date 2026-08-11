from threading import Event

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager


def test_default_directory_selection_does_not_create_a_placeholder(
    monkeypatch, tmp_path
):
    cancel_event = Event()
    manager = object.__new__(Manager)
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    def stop_after_directory(_path):
        cancel_event.set()

    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", stop_after_directory)

    result = Manager.create_bottle(
        manager,
        name="Default",
        environment="custom",
        path=str(tmp_path),
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
        cancel_event=cancel_event,
    )

    assert not result.ok
    assert not result.data["config"].Custom_Path
    assert result.data["config"].Path == "Default"
    assert (tmp_path / "Default").is_dir()


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


@pytest.mark.parametrize(
    "cleanup_succeeds,custom_path",
    [(True, False), (False, False), (False, True)],
)
def test_create_bottle_handles_home_directory_links(
    monkeypatch, tmp_path, cleanup_succeeds, custom_path
):
    cancel_event = Event()
    wait_calls = 0
    host_documents = tmp_path / "host-documents"
    host_documents.mkdir()
    custom_root = tmp_path / "custom"
    bottle_root = custom_root if custom_path else tmp_path
    if custom_path:
        custom_root.mkdir()

    class WineBoot:
        def __init__(self, _config):
            pass

        def init(self):
            profile = bottle_root / "Sandboxed" / "drive_c/users/hostuser"
            profile.mkdir(parents=True)
            (profile / "Documents").symlink_to(host_documents)

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
    if not cleanup_succeeds:
        monkeypatch.setattr(
            manager_module.WineUtils,
            "unlink_user_profile_links",
            lambda _prefix: False,
        )

    result = Manager.create_bottle(
        manager,
        name="Sandboxed",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
        path=str(custom_root) if custom_path else "",
        cancel_event=cancel_event,
    )

    bottle_path = bottle_root / "Sandboxed"
    documents = bottle_path / "drive_c/users/hostuser/Documents"
    assert result.ok is False
    if cleanup_succeeds:
        assert documents.is_dir()
        assert not documents.is_symlink()
    else:
        assert result.message == "Failed to sandbox the bottle user directory."
        assert not bottle_path.exists()
        if custom_path:
            assert not (tmp_path / "Sandboxed").exists()
