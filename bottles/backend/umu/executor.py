import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from bottles.backend.globals import Paths
from bottles.backend.umu.models import UmuGame
from bottles.backend.umu.processes import prefix_has_process
from bottles.backend.umu.proton import UmuProtonCatalog
from bottles.backend.umu.provider import UmuInstallation

RESERVED_ENVIRONMENT_KEYS = frozenset(
    {
        "EXE",
        "GAMEID",
        "PROTONPATH",
        "PROTON_VERB",
        "RUNTIMEPATH",
        "STEAM_COMPAT_APP_ID",
        "STEAM_COMPAT_DATA_PATH",
        "STEAM_COMPAT_INSTALL_PATH",
        "STEAM_COMPAT_MOUNTS",
        "STEAM_COMPAT_SHADER_PATH",
        "STEAM_COMPAT_TOOL_PATHS",
        "STORE",
        "SteamAppId",
        "SteamGameId",
        "UMU_ID",
        "WINEPREFIX",
    }
)


class ReservedEnvironmentError(ValueError):
    pass


class UmuProcessError(RuntimeError):
    pass


class UmuWinetricksError(ValueError):
    pass


_WINETRICKS_VERB_PATTERN = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*(=[a-zA-Z0-9]*)?$")


@dataclass(frozen=True)
class UmuCommand:
    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: Path | None = None


@dataclass
class _TrackedProcess:
    process: subprocess.Popen[str]
    pgid: int
    status: str = "preparing"
    reader: threading.Thread | None = None


class UmuExecutor:
    def __init__(
        self,
        installation: UmuInstallation,
        data_root: str | Path | None = None,
        base_environment: Mapping[str, str] | None = None,
        proton_resolver: Callable[[str], str] | None = None,
    ):
        if not isinstance(installation, UmuInstallation):
            raise TypeError("Invalid UMU installation")
        self.installation = installation
        self.data_root = (
            (
                Path(data_root)
                if data_root is not None
                else Path(Paths.base).joinpath("umu")
            )
            .expanduser()
            .resolve(strict=False)
        )
        environment = os.environ if base_environment is None else base_environment
        if not all(
            isinstance(key, str)
            and isinstance(value, str)
            and bool(key)
            and "\0" not in key
            and "\0" not in value
            and "=" not in key
            for key, value in environment.items()
        ):
            raise ValueError("Invalid base environment")
        self.base_environment = dict(environment)
        self.proton_resolver = proton_resolver or UmuProtonCatalog.validate_value
        self._processes: dict[UUID, _TrackedProcess] = {}
        self._process_lock = threading.Lock()
        self._termination_lock = threading.Lock()

    @staticmethod
    def _absolute_path(path: Path) -> Path:
        return path.expanduser().resolve(strict=False)

    def _environment(self, game: UmuGame, *, prefix_only: bool) -> dict[str, str]:
        overridden = RESERVED_ENVIRONMENT_KEYS.intersection(game.environment)
        if overridden:
            names = ", ".join(sorted(overridden))
            raise ReservedEnvironmentError(
                f"Reserved UMU environment variables cannot be overridden: {names}"
            )

        prefix = game.prefix.resolve(self.data_root)
        environment = self.base_environment.copy()
        for key in RESERVED_ENVIRONMENT_KEYS:
            environment.pop(key, None)
        environment.update(game.environment)
        proton = self.proton_resolver(game.proton)
        environment.update(
            {
                "GAMEID": game.game_id,
                "PROTONPATH": proton,
                "STORE": game.store,
                "WINEPREFIX": str(prefix),
            }
        )
        if not prefix_only:
            install_path = (
                self._absolute_path(game.working_directory)
                if game.working_directory
                else self._absolute_path(game.executable).parent
            )
            environment["STEAM_COMPAT_INSTALL_PATH"] = str(install_path)
        else:
            environment.pop("STEAM_COMPAT_INSTALL_PATH", None)
        return environment

    def prepare(self, game: UmuGame) -> UmuCommand:
        executable = self._absolute_path(game.executable)
        cwd = (
            self._absolute_path(game.working_directory)
            if game.working_directory
            else None
        )
        return UmuCommand(
            argv=(
                str(self.installation.path),
                str(executable),
                *game.arguments,
            ),
            env=self._environment(game, prefix_only=False),
            cwd=cwd,
        )

    def prepare_prefix(self, game: UmuGame) -> UmuCommand:
        return UmuCommand(
            argv=(str(self.installation.path), ""),
            env=self._environment(game, prefix_only=True),
        )

    def prepare_winetricks(self, game: UmuGame, verbs: Sequence[str]) -> UmuCommand:
        if isinstance(verbs, (str, bytes)) or not verbs:
            raise UmuWinetricksError("At least one Winetricks verb is required")
        validated = []
        for verb in verbs:
            if not isinstance(verb, str) or not _WINETRICKS_VERB_PATTERN.fullmatch(
                verb
            ):
                raise UmuWinetricksError(f"Invalid Winetricks verb: {verb}")
            validated.append(verb)
        return UmuCommand(
            argv=(str(self.installation.path), "winetricks", *validated),
            env=self._environment(game, prefix_only=True),
        )

    @staticmethod
    def _status_from_output(game: UmuGame, line: str) -> str | None:
        message = line.casefold()
        if game.executable.name.casefold() in message and line.startswith("Proton: "):
            return "running"
        if "installing winetricks" in message or "using winetricks verb" in message:
            return "configuring"
        if "downloading" in message:
            return "downloading"
        if "extracting" in message or "verifying integrity" in message:
            return "preparing"
        return None

    def _read_output(self, game: UmuGame, tracked: _TrackedProcess) -> None:
        output = getattr(tracked.process, "stdout", None)
        if output is None:
            return
        for line in output:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except (OSError, UnicodeError):
                pass
            status = self._status_from_output(game, line)
            if status is None:
                continue
            with self._process_lock:
                if (
                    self._processes.get(game.id) is tracked
                    and tracked.status != "running"
                ):
                    tracked.status = status

    def _start(self, game: UmuGame, command: UmuCommand) -> subprocess.Popen[str]:
        with self._process_lock:
            running = self._processes.get(game.id)
            if running is not None:
                if self._group_exists(running):
                    raise UmuProcessError(f"UMU game is already running: {game.id}")
                del self._processes[game.id]
            if prefix_has_process(game.prefix.resolve(self.data_root)):
                raise UmuProcessError(f"The UMU prefix is already in use: {game.id}")
            process = subprocess.Popen(
                list(command.argv),
                cwd=str(command.cwd) if command.cwd is not None else None,
                env=command.env.copy(),
                shell=False,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            tracked = _TrackedProcess(process=process, pgid=process.pid)
            self._processes[game.id] = tracked
            tracked.reader = threading.Thread(
                target=self._read_output,
                args=(game, tracked),
                daemon=True,
            )
            tracked.reader.start()
        return process

    def run(self, game: UmuGame) -> subprocess.Popen[str]:
        return self._start(game, self.prepare(game))

    def create_prefix(self, game: UmuGame) -> subprocess.Popen[str]:
        return self._start(game, self.prepare_prefix(game))

    def install_winetricks(
        self, game: UmuGame, verbs: Sequence[str]
    ) -> subprocess.Popen[str]:
        return self._start(game, self.prepare_winetricks(game, verbs))

    def process_for(self, game: UmuGame) -> subprocess.Popen[str] | None:
        with self._process_lock:
            tracked = self._processes.get(game.id)
            if tracked is not None and not self._group_exists(tracked):
                del self._processes[game.id]
                return None
            return tracked.process if tracked is not None else None

    def is_running(self, game: UmuGame) -> bool:
        return self.process_for(game) is not None or prefix_has_process(
            game.prefix.resolve(self.data_root)
        )

    def is_tracked(self, game: UmuGame) -> bool:
        return self.process_for(game) is not None

    def status_for(self, game: UmuGame) -> str | None:
        with self._process_lock:
            tracked = self._processes.get(game.id)
            return tracked.status if tracked is not None else None

    def has_running_processes(self) -> bool:
        with self._process_lock:
            stopped = [
                game_id
                for game_id, tracked in self._processes.items()
                if not self._group_exists(tracked)
            ]
            for game_id in stopped:
                del self._processes[game_id]
            return bool(self._processes)

    def wait(self, game: UmuGame) -> int:
        with self._process_lock:
            tracked = self._processes.get(game.id)
        if tracked is None:
            raise UmuProcessError(f"UMU game is not running: {game.id}")

        return_code = tracked.process.wait()
        while self._group_exists(tracked):
            time.sleep(0.1)
        if tracked.reader is not None:
            tracked.reader.join()
        self._forget(game.id, tracked)
        return return_code

    @staticmethod
    def _group_exists(tracked: _TrackedProcess) -> bool:
        if tracked.process.poll() is None:
            return True
        try:
            os.killpg(tracked.pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _wait_for_group_exit(tracked: _TrackedProcess, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while UmuExecutor._group_exists(tracked):
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        return True

    def _forget(self, game_id: UUID, tracked: _TrackedProcess) -> None:
        with self._process_lock:
            if self._processes.get(game_id) is tracked:
                del self._processes[game_id]

    def terminate(
        self,
        game_or_process: UmuGame | subprocess.Popen[str],
        timeout: float = 5,
    ) -> bool:
        with self._termination_lock:
            return self._terminate(game_or_process, timeout)

    def _terminate(
        self,
        game_or_process: UmuGame | subprocess.Popen[str],
        timeout: float,
    ) -> bool:
        if isinstance(game_or_process, UmuGame):
            with self._process_lock:
                tracked = self._processes.get(game_or_process.id)
            game_id: UUID | None = game_or_process.id
        else:
            with self._process_lock:
                match = next(
                    (
                        (item_id, item)
                        for item_id, item in self._processes.items()
                        if item.process is game_or_process
                    ),
                    None,
                )
            if match is None:
                return False
            game_id, tracked = match

        if tracked is None or game_id is None:
            return False
        if not self._group_exists(tracked):
            self._forget(game_id, tracked)
            return False
        if timeout < 0:
            raise ValueError("Process termination timeout cannot be negative")

        try:
            os.killpg(tracked.pgid, signal.SIGTERM)
        except ProcessLookupError:
            self._forget(game_id, tracked)
            return True

        deadline = time.monotonic() + timeout
        if tracked.process.poll() is None:
            try:
                tracked.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                pass
        remaining = max(0.0, deadline - time.monotonic())
        if not self._wait_for_group_exit(tracked, remaining):
            try:
                os.killpg(tracked.pgid, signal.SIGKILL)
            except ProcessLookupError:
                self._forget(game_id, tracked)
                return True
            if tracked.process.poll() is None:
                try:
                    tracked.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            if not self._wait_for_group_exit(tracked, 1):
                raise UmuProcessError(f"UMU process group did not stop: {tracked.pgid}")

        self._forget(game_id, tracked)
        return True
