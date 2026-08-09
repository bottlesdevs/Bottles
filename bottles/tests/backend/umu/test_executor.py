from dataclasses import replace

import pytest

from bottles.backend.umu import (
    ReservedEnvironmentError,
    UmuExecutor,
    UmuGameRepository,
    UmuInstallation,
    UmuProcessError,
    UmuWinetricksError,
)
from bottles.backend.umu import executor as executor_module


def _game(repository, tmp_path, environment=None):
    return repository.new_game(
        "Example",
        tmp_path / "Game Files" / "game;name.exe",
        proton="GE-Proton",
        game_id="umu-1234",
        store="gog",
        arguments=("--option", "value with spaces", "$(touch ignored)"),
        working_directory=tmp_path / "Game Files",
        environment=environment,
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


def test_prepare_rejects_reserved_environment_override(tmp_path):
    repository = UmuGameRepository(tmp_path / "umu")
    game = _game(repository, tmp_path, {"WINEPREFIX": "/tmp/escape"})
    executor = _executor(repository, tmp_path)

    with pytest.raises(ReservedEnvironmentError, match="WINEPREFIX"):
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
