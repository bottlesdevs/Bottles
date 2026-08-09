import subprocess
from pathlib import Path

import pytest

from bottles.backend.utils.steam import SteamUtils


@pytest.fixture
def runners_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "runners"
    path.mkdir()
    monkeypatch.setattr("bottles.backend.utils.steam.Paths.runners", str(path))
    return path


def _write_toolmanifest(path: Path, require_tool_appid: str | None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    entries = ['"commandline" "/proton %verb%"']
    if require_tool_appid is not None:
        entries.append(f'"require_tool_appid" "{require_tool_appid}"')
    (path / "toolmanifest.vdf").write_text(
        '"manifest"\n{{\n{}\n}}\n'.format("\n".join(entries)),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("require_tool_appid", "expected"),
    [
        ("4183110", "steamrt4"),
        ("1628350", "sniper"),
        ("1391110", "soldier"),
        ("1070560", "scout"),
        (None, "scout"),
    ],
)
def test_associated_runtime_follows_required_tool_appid(
    tmp_path: Path, require_tool_appid: str | None, expected: str
) -> None:
    proton_path = _write_toolmanifest(tmp_path / "Proton", require_tool_appid)

    assert SteamUtils.get_associated_runtime(str(proton_path)) == expected


def test_associated_runtime_is_unknown_without_toolmanifest(tmp_path: Path) -> None:
    proton_path = tmp_path / "Proton"
    proton_path.mkdir()

    assert SteamUtils.get_associated_runtime(str(proton_path)) is None


def test_sync_proton_vkd3d_copies_wined3d_dependencies(tmp_path: Path) -> None:
    proton_path = tmp_path / "Proton"
    default_prefix = proton_path / "files/share/default_pfx/drive_c/windows"
    prefix = tmp_path / "prefix"
    dlls = (
        "libvkd3d-1.dll",
        "libvkd3d-shader-1.dll",
        "libvkd3d-utils-1.dll",
    )
    for directory in ("system32", "syswow64"):
        source = default_prefix / directory
        source.mkdir(parents=True)
        for dll in dlls:
            (source / dll).write_bytes(f"{directory}/{dll}".encode())

    SteamUtils.sync_proton_vkd3d(str(proton_path), str(prefix), "win64")

    for directory in ("system32", "syswow64"):
        for dll in dlls:
            assert (prefix / "drive_c/windows" / directory / dll).read_bytes() == (
                f"{directory}/{dll}".encode()
            )


def _write_protonfixes(path: Path, replacement: str) -> None:
    package = path / "protonfixes"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        f"""import os
from pathlib import Path


def setup_upscalers(compat_config, env, compat_dir, prefix_dir):
    if "fsr4" not in compat_config and "{replacement}" == "WINE_UPSCALER_REPLACE":
        return
    Path(compat_dir, "fsr4_version").write_text("4.0.2", encoding="utf-8")
    dll = Path(prefix_dir, "drive_c/windows/system32/amdxcffx64.dll")
    dll.parent.mkdir(parents=True, exist_ok=True)
    dll.write_bytes(b"fsr4")
    env["FSR4_UPGRADE"] = "1"
    env["{replacement}"] = "fsr4"
    if "{replacement}" == "WINE_LOADDLL_REPLACE":
        enabled = env.get("ENABLE_LAYER_MESA_ANTI_LAG") == "1"
        env.setdefault("DISABLE_LAYER_MESA_ANTI_LAG", "0" if enabled else "1")
    if "mlfg" in compat_config and "{replacement}" == "WINE_UPSCALER_REPLACE":
        env["MLFG_UPGRADE"] = "1"
    if "fsr4rdna3" in compat_config and "{replacement}" == "WINE_LOADDLL_REPLACE":
        env["DXIL_SPIRV_CONFIG"] = "wmma_rdna3_workaround"
    if "BOTTLES_TEST_SECRET" in os.environ:
        Path(compat_dir, "secret_seen").touch()
""",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "replacement",
    ["WINE_LOADDLL_REPLACE", "WINE_UPSCALER_REPLACE"],
)
def test_prepare_proton_fsr4_uses_runner_protonfixes(
    tmp_path: Path, runners_path: Path, replacement: str
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, replacement)
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {
        "PROTON_FSR4_UPGRADE": "4.0.2",
        replacement: "dlss",
    }

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)

    assert (prefix / ".proton/fsr4_version").read_text(encoding="utf-8") == "4.0.2"
    assert (prefix / "drive_c/windows/system32/amdxcffx64.dll").read_bytes() == b"fsr4"
    assert env["FSR4_UPGRADE"] == "1"
    assert env[replacement] == "dlss,fsr4"
    assert (env.get("MLFG_UPGRADE") == "1") is (replacement == "WINE_UPSCALER_REPLACE")


def test_prepare_proton_fsr4_skips_disabled_feature(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(*_args, **_kwargs):
        pytest.fail("protonfixes must not run")

    monkeypatch.setattr("bottles.backend.utils.steam.subprocess.Popen", fail)

    assert not SteamUtils.prepare_proton_fsr4(
        str(tmp_path / "GE-Proton"),
        str(tmp_path / "prefix"),
        {"PROTON_FSR4_UPGRADE": "0"},
    )


def test_prepare_proton_fsr4_sets_rdna3_workaround(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_LOADDLL_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {"PROTON_FSR4_RDNA3_UPGRADE": "1"}

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert env["DXIL_SPIRV_CONFIG"] == "wmma_rdna3_workaround"


def test_prepare_proton_fsr4_does_not_promote_unsupported_rdna3(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {"PROTON_FSR4_RDNA3_UPGRADE": "1"}

    assert not SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert "FSR4_UPGRADE" not in env


def test_prepare_proton_fsr4_preserves_mesa_anti_lag_choice(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_LOADDLL_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {
        "PROTON_FSR4_UPGRADE": "1",
        "ENABLE_LAYER_MESA_ANTI_LAG": "1",
    }

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert env["DISABLE_LAYER_MESA_ANTI_LAG"] == "0"


def test_prepare_proton_fsr4_preserves_mesa_anti_lag_disable_override(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_LOADDLL_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {
        "PROTON_FSR4_UPGRADE": "1",
        "DISABLE_LAYER_MESA_ANTI_LAG": "0",
    }

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert env["DISABLE_LAYER_MESA_ANTI_LAG"] == "0"


def test_prepare_proton_fsr4_accepts_existing_output(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {
        "PROTON_FSR4_UPGRADE": "1",
        "FSR4_UPGRADE": "1",
        "WINE_UPSCALER_REPLACE": "fsr4",
    }

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert env["FSR4_UPGRADE"] == "1"
    assert env["WINE_UPSCALER_REPLACE"] == "fsr4"


def test_prepare_proton_fsr4_isolates_prefix_imports(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (prefix / "json.py").write_text(
        'open("shadowed", "w").write("loaded")\nraise RuntimeError\n',
        encoding="utf-8",
    )

    assert SteamUtils.prepare_proton_fsr4(
        str(proton_path),
        str(prefix),
        {"PROTON_FSR4_UPGRADE": "1"},
    )
    assert not (prefix / "shadowed").exists()


def test_prepare_proton_fsr4_filters_host_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    monkeypatch.setenv("BOTTLES_TEST_SECRET", "must-not-leak")

    assert SteamUtils.prepare_proton_fsr4(
        str(proton_path),
        str(prefix),
        {"PROTON_FSR4_UPGRADE": "1"},
    )
    assert not (prefix / ".proton/secret_seen").exists()


def test_prepare_proton_fsr4_rejects_incomplete_setup(
    tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    package = proton_path / "protonfixes"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "def setup_upscalers(*_args):\n    return None\n",
        encoding="utf-8",
    )
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    env = {"PROTON_FSR4_UPGRADE": "1"}

    assert not SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert "FSR4_UPGRADE" not in env


def test_prepare_proton_fsr4_rejects_unmanaged_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = tmp_path / "prefix/GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    env = {"PROTON_FSR4_UPGRADE": "1"}

    def fail(*_args, **_kwargs):
        pytest.fail("unmanaged protonfixes must not run")

    monkeypatch.setattr("bottles.backend.utils.steam.subprocess.Popen", fail)

    assert not SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env)
    assert "FSR4_UPGRADE" not in env


def test_prepare_proton_fsr4_rejects_runner_symlink_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = tmp_path / "unmanaged/GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    runner_link = runners_path / "GE-Proton"
    runner_link.symlink_to(proton_path, target_is_directory=True)
    prefix = tmp_path / "prefix"
    prefix.mkdir()

    def fail(*_args, **_kwargs):
        pytest.fail("symlinked protonfixes must not run")

    monkeypatch.setattr("bottles.backend.utils.steam.subprocess.Popen", fail)

    assert not SteamUtils.prepare_proton_fsr4(
        str(runner_link), str(prefix), {"PROTON_FSR4_UPGRADE": "1"}
    )


def test_prepare_proton_fsr4_rejects_protonfixes_symlink_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    proton_path.mkdir()
    external_path = tmp_path / "unmanaged/GE-Proton"
    _write_protonfixes(external_path, "WINE_UPSCALER_REPLACE")
    (proton_path / "protonfixes").symlink_to(
        external_path / "protonfixes", target_is_directory=True
    )
    prefix = tmp_path / "prefix"
    prefix.mkdir()

    def fail(*_args, **_kwargs):
        pytest.fail("symlinked protonfixes must not run")

    monkeypatch.setattr("bottles.backend.utils.steam.subprocess.Popen", fail)

    assert not SteamUtils.prepare_proton_fsr4(
        str(proton_path), str(prefix), {"PROTON_FSR4_UPGRADE": "1"}
    )


def test_prepare_proton_fsr4_uses_dedicated_sandbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    dll = prefix / "drive_c/windows/system32/amdxcffx64.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"fsr4")
    marker = (
        b'BOTTLES_PROTON_ENV={"FSR4_UPGRADE":"1",' b'"WINE_UPSCALER_REPLACE":"fsr4"}\n'
    )
    called = {}

    class Process:
        returncode = 0

        @staticmethod
        def communicate(timeout):
            called["timeout"] = timeout
            return marker, b""

    class Sandbox:
        envs = None

        @staticmethod
        def run(command):
            called["command"] = command
            return Process()

    def fail(*_args, **_kwargs):
        pytest.fail("protonfixes must run through the dedicated sandbox")

    monkeypatch.setattr("bottles.backend.utils.steam.subprocess.Popen", fail)
    sandbox = Sandbox()
    env = {"PROTON_FSR4_UPGRADE": "1"}

    assert SteamUtils.prepare_proton_fsr4(str(proton_path), str(prefix), env, sandbox)
    assert called["timeout"] == 120
    assert str(proton_path) in called["command"]
    assert sandbox.envs == {
        "HOME": str(prefix / ".proton"),
        "PROTON_FSR4_UPGRADE": "1",
    }
    assert env["FSR4_UPGRADE"] == "1"
    assert env["WINE_UPSCALER_REPLACE"] == "fsr4"


def test_prepare_proton_fsr4_kills_process_group_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runners_path: Path
) -> None:
    proton_path = runners_path / "GE-Proton"
    _write_protonfixes(proton_path, "WINE_UPSCALER_REPLACE")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    called = {"communicate": 0}

    class Process:
        pid = 42
        returncode = -9

        @staticmethod
        def communicate(timeout=None):
            called["communicate"] += 1
            if called["communicate"] == 1:
                raise subprocess.TimeoutExpired("protonfixes", 120)
            return b"", b""

    monkeypatch.setattr(
        "bottles.backend.utils.steam.subprocess.Popen",
        lambda *_args, **_kwargs: Process(),
    )
    monkeypatch.setattr(
        "bottles.backend.utils.steam.os.killpg",
        lambda pgid, sig: called.update({"pgid": pgid, "signal": sig}),
    )

    assert not SteamUtils.prepare_proton_fsr4(
        str(proton_path), str(prefix), {"PROTON_FSR4_UPGRADE": "1"}
    )
    assert called == {
        "communicate": 2,
        "pgid": 42,
        "signal": 9,
    }
