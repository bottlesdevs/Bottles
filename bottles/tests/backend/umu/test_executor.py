from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from bottles.backend.umu import (
    ReservedEnvironmentError,
    UmuExecutor,
    UmuGame,
    UmuGameRepository,
    UmuInstallation,
    UmuPrefix,
    UmuProcessError,
    UmuWinetricksError,
)
from bottles.backend.umu import executor as executor_module
from bottles.backend.utils import vdf


def _game(repository, tmp_path, environment=None, sandbox=False, share_net=False):
    return repository.new_game(
        "Example",
        tmp_path / "Game Files" / "game;name.exe",
        proton="GE-Proton",
        game_id="umu-1234",
        store="gog",
        arguments=("--option", "value with spaces", "$(touch ignored)"),
        working_directory=tmp_path / "Game Files",
        environment=environment,
        sandbox=sandbox,
        share_net=share_net,
    )


def _executor(repository, tmp_path, base_environment=None):
    installation = UmuInstallation(
        path=tmp_path / "umu launcher" / "umu-run",
        version="1.4.4",
        source="managed",
    )
    return UmuExecutor(
        installation,
        data_root=repository.root,
        base_environment=base_environment or {"DISPLAY": ":1"},
    )


def _installed_proton(tmp_path, require_tool_appid=None):
    proton = tmp_path / "runners" / "protosoda-11.0-1"
    proton.mkdir(parents=True)
    proton.joinpath("proton").touch()
    proton.joinpath("files").mkdir()
    runtime = (
        f'  "require_tool_appid" "{require_tool_appid}"\n' if require_tool_appid else ""
    )
    proton.joinpath("toolmanifest.vdf").write_text(
        '"manifest"\n'
        "{\n"
        '  "version" "2"\n'
        '  "commandline" "/proton %verb%"\n'
        f"{runtime}"
        '  "use_sessions" "1"\n'
        '  "compatmanager_layer_name" "proton"\n'
        "}\n"
    )
    return proton


def test_prepare_builds_argv_without_shell_expansion(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, {"PROTON_LOG": "1"})
    executor = _executor(repository, tmp_path)

    command = executor.prepare(game)

    assert command.argv == (
        str(executor.installation.path),
        str(game.executable.resolve()),
        "--option",
        "value with spaces",
        "$(touch ignored)",
    )
    assert command.cwd == game.working_directory.resolve()
    assert command.env["DISPLAY"] == ":1"
    assert command.env["PROTON_LOG"] == "1"
    assert command.env["WINEPREFIX"] == str(repository.prefix_path(game))
    assert command.env["GAMEID"] == "umu-1234"
    assert command.env["STORE"] == "gog"
    assert command.env["PROTONPATH"] == "GE-Proton"
    assert "UMU_NO_RUNTIME" not in command.env
    assert command.env["STEAM_COMPAT_INSTALL_PATH"] == str(command.cwd)


def test_prepare_resolves_managed_proton(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = replace(_game(repository, tmp_path), proton="ProtoSoda")
    proton = tmp_path / "ProtoSoda"
    proton.mkdir()
    installation = UmuInstallation(
        path=tmp_path / "umu-run",
        version="1.4.4",
        source="managed",
    )
    executor = UmuExecutor(
        installation,
        data_root=repository.root,
        base_environment={},
        proton_resolver=lambda value: str(proton) if value == "ProtoSoda" else value,
    )

    assert executor.prepare(game).env["PROTONPATH"] == str(proton)


def test_prepare_enables_adaptive_launch_for_protosoda(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = replace(_game(repository, tmp_path), proton="ProtoSoda")
    proton = tmp_path / "runners" / "protosoda-11.0-2"
    prepared = {}

    class FakeProfile:
        @classmethod
        def from_root(cls, root, runner, executable):
            prepared.update(
                root=root,
                runner=runner,
                executable=executable,
            )
            profile = cls()
            profile.trace_dir = tmp_path / "trace"
            return profile

        def prepare(self):
            prepared["called"] = True
            return 2

    monkeypatch.setattr(executor_module, "AdaptiveLaunchProfile", FakeProfile)
    executor = UmuExecutor(
        UmuInstallation(
            path=tmp_path / "umu-run",
            version="1.4.4",
            source="managed",
        ),
        data_root=repository.root,
        base_environment={},
        proton_resolver=lambda _value: str(proton),
    )

    command = executor.prepare(game)

    assert prepared == {
        "root": repository.prefix_path(game),
        "runner": "protosoda-11.0-2",
        "executable": str(game.executable.resolve()),
        "called": True,
    }
    assert command.env["SODA_ADAPTIVE_TRACE_DIR"] == str(tmp_path / "trace")


def test_prepare_does_not_enable_adaptive_launch_for_old_protosoda(
    monkeypatch, tmp_path
):
    repository = UmuGameRepository(tmp_path / "umu")
    game = replace(_game(repository, tmp_path), proton="ProtoSoda")
    proton = tmp_path / "runners" / "protosoda-11.0-1"
    monkeypatch.setattr(
        executor_module,
        "AdaptiveLaunchProfile",
        lambda *_args, **_kwargs: pytest.fail("profile should not be created"),
    )
    executor = UmuExecutor(
        UmuInstallation(
            path=tmp_path / "umu-run",
            version="1.4.4",
            source="managed",
        ),
        data_root=repository.root,
        base_environment={},
        proton_resolver=lambda _value: str(proton),
    )

    command = executor.prepare(game)

    assert "SODA_ADAPTIVE_TRACE_DIR" not in command.env


def test_prepare_rejects_adaptive_trace_override(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(
        repository,
        tmp_path,
        {"SODA_ADAPTIVE_TRACE_DIR": "/tmp/escape"},
    )
    executor = _executor(repository, tmp_path)

    with pytest.raises(ReservedEnvironmentError, match="SODA_ADAPTIVE_TRACE_DIR"):
        executor.prepare(game)


def test_prepare_rejects_reserved_environment_override(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, {"WINEPREFIX": "/tmp/escape"})
    executor = _executor(repository, tmp_path)

    with pytest.raises(ReservedEnvironmentError, match="WINEPREFIX"):
        executor.prepare(game)


def test_prepare_rejects_runtime_override(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, {"UMU_NO_RUNTIME": "1"})
    executor = _executor(repository, tmp_path)

    with pytest.raises(ReservedEnvironmentError, match="UMU_NO_RUNTIME"):
        executor.prepare(game)


def test_prepare_replaces_reserved_base_environment(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(
        repository,
        tmp_path,
        {"WINEPREFIX": "/stale", "GAMEID": "old", "DISPLAY": ":2"},
    )

    command = executor.prepare(game)

    assert command.env["WINEPREFIX"] == str(repository.prefix_path(game))
    assert command.env["GAMEID"] == "umu-1234"
    assert command.env["DISPLAY"] == ":2"


def test_prepare_removes_missing_session_bus(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(
        repository,
        tmp_path,
        {"DBUS_SESSION_BUS_ADDRESS": f"unix:path={tmp_path / 'missing-bus'}"},
    )

    command = executor.prepare(game)

    assert "DBUS_SESSION_BUS_ADDRESS" not in command.env


def test_prepare_preserves_existing_session_bus(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    bus = tmp_path / "bus"
    bus.touch()
    address = f"unix:path={bus}"
    executor = _executor(
        repository,
        tmp_path,
        {"DBUS_SESSION_BUS_ADDRESS": address},
    )

    command = executor.prepare(game)

    assert command.env["DBUS_SESSION_BUS_ADDRESS"] == address


def test_prepare_prefix_uses_empty_executable(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    command = executor.prepare_prefix(game)

    assert command.argv == (str(executor.installation.path), "")
    assert command.cwd is None
    assert "STEAM_COMPAT_INSTALL_PATH" not in command.env


def test_prepare_winetricks_uses_validated_argv(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    command = executor.prepare_winetricks(game, ["vcrun2022", "win10=", "d3dx9_43"])

    assert command.argv == (
        str(executor.installation.path),
        "winetricks",
        "vcrun2022",
        "win10=",
        "d3dx9_43",
    )
    assert command.cwd is None
    assert "STEAM_COMPAT_INSTALL_PATH" not in command.env


@pytest.mark.parametrize(
    "verbs",
    [[], "vcrun2022", ["bad verb"], ["foo;touch"], ["--help"], ["-q"]],
)
def test_prepare_winetricks_rejects_invalid_verbs(tmp_path, verbs):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    with pytest.raises(UmuWinetricksError):
        executor.prepare_winetricks(game, verbs)


def test_run_uses_popen_without_shell(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

    process = Process()
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return process

    monkeypatch.setattr(executor_module.subprocess, "Popen", popen)

    assert executor.run(game) is process
    argv, kwargs = calls[0]
    assert argv == list(executor.prepare(game).argv)
    assert kwargs["shell"] is False
    assert kwargs["start_new_session"] is True
    assert kwargs["stdout"] is executor_module.subprocess.PIPE
    assert kwargs["stderr"] is executor_module.subprocess.STDOUT
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["cwd"] == str(game.working_directory.resolve())


def test_run_uses_dedicated_sandbox_when_enabled(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    game = _game(repository, tmp_path, sandbox=True)
    executor = _executor(
        repository,
        tmp_path,
        {"DISPLAY": ":1", "XDG_DATA_HOME": str(tmp_path / "data")},
    )

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

    calls = []
    runtime_commands = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return Process()

    monkeypatch.setattr(executor, "_ensure_sandbox_runtime", runtime_commands.append)
    monkeypatch.setattr(executor_module.subprocess, "Popen", popen)

    executor.run(game)

    argv, kwargs = calls[0]
    assert len(runtime_commands) == 1
    assert runtime_commands[0].env["PROTONPATH"] == "GE-Proton"
    prefix = repository.prefix_path(game)
    assert argv.startswith("bwrap --clearenv")
    assert f"--bind {prefix} {prefix}" in argv
    assert f"--ro-bind {tmp_path / 'data' / 'umu'} {tmp_path / 'data' / 'umu'}" in argv
    assert "--ro-bind / /" not in argv
    assert "--unshare-net" in argv
    assert "'$(touch ignored)'" in argv
    assert kwargs["shell"] is True
    assert kwargs["start_new_session"] is True


def test_dedicated_sandbox_exposes_managed_proton(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    game = replace(_game(repository, tmp_path, sandbox=True), proton="ProtoSoda")
    proton = _installed_proton(tmp_path, "4183110")
    installation = UmuInstallation(
        path=tmp_path / "umu-run",
        version="1.4.4",
        source="managed",
    )
    executor = UmuExecutor(
        installation,
        data_root=repository.root,
        base_environment={"XDG_DATA_HOME": str(tmp_path / "data")},
        proton_resolver=lambda value: str(proton) if value == "ProtoSoda" else value,
    )

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return Process()

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(executor, "_ensure_sandbox_runtime", lambda _command: None)
    monkeypatch.setattr(executor_module.subprocess, "Popen", popen)

    executor.run(game)

    argv, _kwargs = calls[0]
    command = executor.prepare(game)
    sandbox_proton = Path(command.env["PROTONPATH"])
    assert command.env["UMU_NO_RUNTIME"] == "1"
    assert sandbox_proton != proton
    assert f"--sandbox-expose-path-ro={proton}" in argv
    assert f"--sandbox-expose-path-ro={sandbox_proton}" in argv
    assert "--sandbox-expose-path-ro=/ " not in argv
    assert sandbox_proton.joinpath("proton").resolve() == proton / "proton"
    assert sandbox_proton.joinpath("files").resolve() == proton / "files"
    manifest = vdf.loads(sandbox_proton.joinpath("toolmanifest.vdf").read_text())[
        "manifest"
    ]
    assert "require_tool_appid" not in manifest


def test_flatpak_sandbox_keeps_proton_without_required_runtime(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    game = replace(_game(repository, tmp_path, sandbox=True), proton="ProtoSoda")
    proton = _installed_proton(tmp_path)
    executor = UmuExecutor(
        UmuInstallation(
            path=tmp_path / "umu-run",
            version="1.4.4",
            source="managed",
        ),
        data_root=repository.root,
        base_environment={"FLATPAK_ID": "com.usebottles.bottles"},
        proton_resolver=lambda _value: str(proton),
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    command = executor.prepare(game)

    assert command.env["PROTONPATH"] == str(proton.resolve())
    assert command.env["UMU_NO_RUNTIME"] == "1"
    assert command.readable_paths == (proton.resolve(),)


def test_flatpak_sandbox_rejects_downloadable_proton(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    game = _game(repository, tmp_path, sandbox=True)
    executor = _executor(
        repository,
        tmp_path,
        {"FLATPAK_ID": "com.usebottles.bottles"},
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    with pytest.raises(UmuProcessError, match="installed Proton"):
        executor.prepare(game)


def test_flatpak_sandbox_rejects_filesystem_root(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, sandbox=True)
    executor = UmuExecutor(
        UmuInstallation(
            path=tmp_path / "umu-run",
            version="1.4.4",
            source="managed",
        ),
        data_root=repository.root,
        base_environment={"FLATPAK_ID": "com.usebottles.bottles"},
        proton_resolver=lambda _value: "/",
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    with pytest.raises(UmuProcessError, match="filesystem root"):
        executor.prepare(game)


def test_dedicated_sandbox_uses_flatpak_umu_path(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    proton = _installed_proton(tmp_path)
    game = replace(
        _game(repository, tmp_path, sandbox=True),
        proton=str(proton),
    )
    home = tmp_path / "home"
    executor = _executor(
        repository,
        tmp_path,
        {
            "container": "flatpak",
            "HOME": str(home),
            "XDG_DATA_HOME": str(tmp_path / "flatpak-data"),
        },
    )

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return Process()

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(executor, "_ensure_sandbox_runtime", lambda _command: None)
    monkeypatch.setattr(executor_module.subprocess, "Popen", popen)

    executor.run(game)

    argv, _kwargs = calls[0]
    runtime = home / ".local" / "share" / "umu"
    assert f"--sandbox-expose-path-ro={runtime}" in argv
    assert f"--sandbox-expose-path={runtime}" not in argv
    assert f"--sandbox-expose-path={tmp_path / 'flatpak-data' / 'umu'}" not in argv
    assert "--no-network" in argv


def test_dedicated_sandbox_can_share_network(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    proton = _installed_proton(tmp_path)
    game = replace(
        _game(repository, tmp_path, sandbox=True, share_net=True),
        proton=str(proton),
    )
    executor = _executor(
        repository,
        tmp_path,
        {
            "container": "flatpak",
            "HOME": str(tmp_path / "home"),
            "XDG_DATA_HOME": str(tmp_path / "flatpak-data"),
        },
    )

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    command = executor.prepare(game)

    assert "--no-network" not in executor._sandbox_manager(game, command).get_cmd(
        "true"
    )


def test_dedicated_sandbox_exposes_base_cache(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    cache_home = tmp_path / "cache"
    game = _game(repository, tmp_path, sandbox=True)
    executor = _executor(
        repository,
        tmp_path,
        {"DISPLAY": ":1", "XDG_CACHE_HOME": str(cache_home)},
    )
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    command = executor._sandbox_manager(game, executor.prepare(game)).get_cmd("true")

    assert cache_home.is_dir()
    assert f"--bind {cache_home} {cache_home}" in command


def test_dedicated_sandbox_does_not_expose_game_cache_override(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    base_cache = tmp_path / "base-cache"
    game_cache = tmp_path / "game-cache"
    game = _game(
        repository,
        tmp_path,
        environment={"XDG_CACHE_HOME": str(game_cache)},
        sandbox=True,
    )
    executor = _executor(
        repository,
        tmp_path,
        {"DISPLAY": ":1", "XDG_CACHE_HOME": str(base_cache)},
    )
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    command = executor._sandbox_manager(game, executor.prepare(game)).get_cmd("true")

    assert f"--bind {base_cache} {base_cache}" in command
    assert f"--bind {game_cache} {game_cache}" not in command


def test_dedicated_sandbox_does_not_expose_root_as_cache(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game_folder = tmp_path / "Game Files"
    game_folder.mkdir()
    game = _game(repository, tmp_path, sandbox=True)
    executor = _executor(
        repository,
        tmp_path,
        {"DISPLAY": ":1", "XDG_CACHE_HOME": "/"},
    )
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    command = executor._sandbox_manager(game, executor.prepare(game)).get_cmd("true")

    assert "--bind / /" not in command


def test_runtime_root_uses_flatpak_host_data_home(tmp_path):
    host_data_home = tmp_path / "host-data"

    runtime = UmuExecutor._runtime_root(
        {
            "container": "flatpak",
            "HOME": str(tmp_path / "home"),
            "HOST_XDG_DATA_HOME": str(host_data_home),
            "XDG_DATA_HOME": str(tmp_path / "flatpak-data"),
        }
    )

    assert runtime == host_data_home / "umu"


def test_dedicated_sandbox_prepares_runtime_outside_sandbox(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    proton = _installed_proton(tmp_path)
    game = replace(
        _game(repository, tmp_path, sandbox=True),
        proton=str(proton),
    )
    home = tmp_path / "home"
    executor = _executor(
        repository,
        tmp_path,
        {"container": "flatpak", "HOME": str(home)},
    )
    calls = []

    class Process:
        stdout = iter(())

        @staticmethod
        def wait():
            return 0

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        Path(argv[-1]).touch()
        return Process()

    monkeypatch.setattr(executor_module.subprocess, "Popen", popen)
    command = executor.prepare(game)

    executor._ensure_sandbox_runtime(command)
    executor._ensure_sandbox_runtime(command)
    other_command = replace(
        command,
        env={**command.env, "UMU_FOLDERS_PATH": str(tmp_path / "other-data")},
    )
    executor._ensure_sandbox_runtime(other_command)

    assert len(calls) == 2
    argv, kwargs = calls[0]
    assert argv[:2] == [str(executor.installation.path), "/usr/bin/touch"]
    assert Path(argv[-1]).parent == home / ".local" / "share" / "umu"
    assert not Path(argv[-1]).exists()
    assert kwargs["env"]["UMU_NO_PROTON"] == "1"
    assert kwargs["shell"] is False
    assert Path(calls[1][0][-1]).parent == tmp_path / "other-data" / "umu"


def test_dedicated_sandbox_rejects_incomplete_runtime_setup(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, sandbox=True)
    executor = _executor(repository, tmp_path)

    class Process:
        stdout = iter(("ERROR: umu has not been setup for the user\n",))

        @staticmethod
        def wait():
            return 0

    monkeypatch.setattr(
        executor_module.subprocess,
        "Popen",
        lambda _argv, **_kwargs: Process(),
    )

    with pytest.raises(UmuProcessError, match="UMU runtime setup failed"):
        executor._ensure_sandbox_runtime(executor.prepare(game))


def test_dedicated_sandbox_rejects_filesystem_root_as_prefix(monkeypatch, tmp_path):
    game = UmuGame(
        id=uuid4(),
        name="Unsafe prefix",
        executable=tmp_path / "game.exe",
        prefix=UmuPrefix("/", managed=False),
        proton="UMU-Proton",
        sandbox=True,
    )
    executor = _executor(UmuGameRepository(tmp_path / "umu"), tmp_path)
    monkeypatch.setattr(executor_module, "prefix_has_process", lambda _prefix: False)

    with pytest.raises(UmuProcessError, match="filesystem root"):
        executor.run(game)


@pytest.mark.parametrize(
    ("line", "status"),
    [
        ("INFO: Downloading UMU-Proton.tar.gz...", "downloading"),
        ("INFO: Extracting UMU-Proton.tar.gz...", "preparing"),
        ("INFO: Installing winetricks dotnetdesktop9", "configuring"),
        ("Proton: /games/game;name.exe", "running"),
        ("INFO: Using UMU-Proton", None),
    ],
)
def test_executor_maps_output_to_install_status(tmp_path, line, status):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)

    assert UmuExecutor._status_from_output(game, line) == status


def test_executor_keeps_running_status_after_late_setup_output(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class Output:
        stdout = iter(
            (
                "Proton: /games/game;name.exe\n",
                "INFO: Downloading a late cache file\n",
            )
        )

    tracked = executor_module._TrackedProcess(Output(), 1)
    executor._processes[game.id] = tracked

    executor._read_output(game, tracked)

    assert tracked.status == "running"


def test_executor_drains_output_when_terminal_write_fails(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class BrokenOutput:
        def write(self, _line):
            raise OSError("terminal closed")

        def flush(self):
            raise AssertionError("flush must not run after a failed write")

    class Process:
        stdout = iter(("INFO: Downloading Proton\n", "Proton: game;name.exe\n"))

    tracked = executor_module._TrackedProcess(Process(), 1)
    executor._processes[game.id] = tracked
    monkeypatch.setattr(executor_module.sys, "stdout", BrokenOutput())

    executor._read_output(game, tracked)

    assert tracked.status == "running"


def test_executor_rejects_duplicate_running_game(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class Process:
        pid = 123

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(
        executor_module.subprocess, "Popen", lambda *_a, **_kw: Process()
    )

    executor.run(game)

    with pytest.raises(UmuProcessError, match="already running"):
        executor.run(game)


def test_executor_rejects_prefix_used_by_another_session(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)
    monkeypatch.setattr(executor_module, "prefix_has_process", lambda _prefix: True)

    with pytest.raises(UmuProcessError, match="prefix is already in use"):
        executor.run(game)


def test_terminate_stops_tracked_process_group(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)
    signals = []

    class Process:
        pid = 321
        running = True

        def poll(self):
            return None if self.running else 0

        def wait(self, timeout=None):
            self.running = False
            return 0

    process = Process()
    monkeypatch.setattr(executor_module.subprocess, "Popen", lambda *_a, **_kw: process)

    def killpg(pid, sent_signal):
        if sent_signal == 0 and not process.running:
            raise ProcessLookupError
        if sent_signal != 0:
            signals.append((pid, sent_signal))

    monkeypatch.setattr(executor_module.os, "killpg", killpg)
    executor.run(game)

    assert executor.is_running(game) is True
    assert executor.terminate(game) is True
    assert executor.is_running(game) is False
    assert signals == [(321, executor_module.signal.SIGTERM)]


def test_terminate_kills_process_group_after_timeout(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)
    signals = []

    class Process:
        pid = 456
        running = True

        def poll(self):
            return None if self.running else 0

        def wait(self, timeout=None):
            if timeout is not None:
                raise executor_module.subprocess.TimeoutExpired("umu-run", timeout)
            self.running = False
            return 0

    process = Process()
    monkeypatch.setattr(executor_module.subprocess, "Popen", lambda *_a, **_kw: process)

    def killpg(pid, sent_signal):
        if sent_signal == 0 and not process.running:
            raise ProcessLookupError
        if sent_signal == executor_module.signal.SIGKILL:
            process.running = False
        if sent_signal != 0:
            signals.append((pid, sent_signal))

    monkeypatch.setattr(executor_module.os, "killpg", killpg)
    executor.run(game)

    assert executor.terminate(process, timeout=0.1) is True
    assert signals == [
        (456, executor_module.signal.SIGTERM),
        (456, executor_module.signal.SIGKILL),
    ]


def test_executor_tracks_live_group_after_leader_exits(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)
    group_running = True

    class Process:
        pid = 654

        @staticmethod
        def poll():
            return 0

    process = Process()
    monkeypatch.setattr(executor_module.subprocess, "Popen", lambda *_a, **_kw: process)

    def killpg(_pid, sent_signal):
        nonlocal group_running
        if sent_signal == 0 and not group_running:
            raise ProcessLookupError
        if sent_signal == executor_module.signal.SIGTERM:
            group_running = False

    monkeypatch.setattr(executor_module.os, "killpg", killpg)
    executor.run(game)

    assert executor.is_running(game) is True
    assert executor.terminate(game) is True
    assert executor.is_running(game) is False


def test_wait_tracks_process_group_until_every_process_exits(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)
    group_checks = iter((True, False))

    class Process:
        pid = 655

        @staticmethod
        def poll():
            return 7

        @staticmethod
        def wait():
            return 7

    monkeypatch.setattr(
        executor_module.subprocess, "Popen", lambda *_a, **_kw: Process()
    )

    def killpg(_pid, sent_signal):
        if sent_signal == 0 and not next(group_checks):
            raise ProcessLookupError

    monkeypatch.setattr(executor_module.os, "killpg", killpg)
    monkeypatch.setattr(executor_module.time, "sleep", lambda _seconds: None)
    executor.run(game)

    assert executor.wait(game) == 7
    assert executor.is_running(game) is False


def test_has_running_processes_prunes_completed_groups(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class Process:
        pid = 656

        @staticmethod
        def poll():
            return 0

    monkeypatch.setattr(
        executor_module.subprocess, "Popen", lambda *_a, **_kw: Process()
    )
    monkeypatch.setattr(
        executor_module.os,
        "killpg",
        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()),
    )
    executor.run(game)

    assert executor.has_running_processes() is False


def test_terminate_keeps_tracking_when_signal_fails(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    executor = _executor(repository, tmp_path)

    class Process:
        pid = 987

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(
        executor_module.subprocess, "Popen", lambda *_a, **_kw: Process()
    )
    executor.run(game)
    monkeypatch.setattr(
        executor_module.os,
        "killpg",
        lambda _pid, _sent_signal: (_ for _ in ()).throw(PermissionError()),
    )

    with pytest.raises(PermissionError):
        executor.terminate(game)

    assert executor.process_for(game) is not None


def test_terminate_does_not_signal_untracked_process(monkeypatch, tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    executor = _executor(repository, tmp_path)
    signals = []

    class Process:
        pid = 789

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(
        executor_module.os,
        "killpg",
        lambda pid, sent_signal: signals.append((pid, sent_signal)),
    )

    assert executor.terminate(Process()) is False
    assert signals == []


def test_executor_does_not_mutate_supplied_environment(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path)
    base_environment = {"DISPLAY": ":3"}
    executor = _executor(repository, tmp_path, base_environment)

    executor.prepare(game)

    assert base_environment == {"DISPLAY": ":3"}


def test_executor_rejects_invalid_base_environment_name(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")

    with pytest.raises(ValueError, match="Invalid base environment"):
        _executor(repository, tmp_path, {"BAD=NAME": "value"})

    with pytest.raises(ValueError, match="Invalid base environment"):
        _executor(repository, tmp_path, {"": "value"})


def test_game_rejects_invalid_environment_name(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")

    with pytest.raises(ValueError, match="Invalid environment key"):
        _game(repository, tmp_path, {"BAD=NAME": "value"})
