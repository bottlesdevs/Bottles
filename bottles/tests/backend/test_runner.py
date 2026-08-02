from bottles.backend import runner as runner_module
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.runner import Runner


def test_runner_update_unlinks_only_new_user_profile(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    users = prefix / "drive_c" / "users"
    existing = users / "mirko"
    existing.mkdir(parents=True)
    existing_target = tmp_path / "existing-target"
    existing_target.mkdir()
    (existing / "Custom").symlink_to(existing_target)
    host_documents = tmp_path / "host-documents"
    host_documents.mkdir()
    keep_link = host_documents / "keep-link"
    keep_link.symlink_to(existing_target)

    class WineBoot:
        def __init__(self, _config):
            pass

        def kill(self, force_if_stalled=False):
            late_profile = users / "late-profile"
            late_profile.mkdir()
            (late_profile / "Custom").symlink_to(existing_target)

        def update(self):
            created = users / "steamuser"
            created.mkdir()
            (created / "Documents").symlink_to(host_documents)
            windows = created / "AppData" / "Roaming" / "Microsoft" / "Windows"
            windows.mkdir(parents=True)
            (windows / "Templates").symlink_to(existing_target)

    class Manager:
        @staticmethod
        def update_config(config, key, value, scope=""):
            setattr(config, key, value)
            return Result(True, data={"config": config})

        @staticmethod
        def install_dll_component(*_args, **_kwargs):
            raise AssertionError("DLL components are disabled in this fixture")

    config = BottleConfig(
        Name="Test",
        Path=str(prefix),
        Custom_Path=True,
        Environment="Custom",
        Runner="soda-9.0",
    )
    monkeypatch.setattr(runner_module, "WineBoot", WineBoot)
    monkeypatch.setattr(
        runner_module.RuntimeManager, "get_runtimes", lambda _runtime: []
    )
    monkeypatch.setattr(
        runner_module.SteamUtils, "is_proton", lambda _runner_path: False
    )

    result = Runner.runner_update(config, Manager(), "sys-wine")

    created = users / "steamuser"
    assert result.ok is True
    assert (existing / "Custom").is_symlink()
    assert (users / "late-profile" / "Custom").is_symlink()
    assert (created / "Documents").is_dir()
    assert not (created / "Documents").is_symlink()
    assert (created / "AppData/Roaming/Microsoft/Windows/Templates").is_dir()
    assert keep_link.is_symlink()
