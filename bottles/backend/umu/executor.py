import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from bottles.backend.globals import Paths
from bottles.backend.managers.sandbox import SandboxManager
from bottles.backend.umu.models import UmuGame
from bottles.backend.umu.processes import prefix_has_process
from bottles.backend.umu.proton import UmuProtonCatalog
from bottles.backend.umu.provider import UmuInstallation
from bottles.backend.utils import vdf
from bottles.backend.wine.adaptive import (
    PROFILE_ENV,
    TRACE_ENV,
    AdaptiveLaunchProfile,
    is_v2_runner,
)

RESERVED_ENVIRONMENT_KEYS = frozenset(
    {
        "EXE",
        "GAMEID",
        "PROTONPATH",
        "PROTON_VERB",
        "RUNTIMEPATH",
        PROFILE_ENV,
        TRACE_ENV,
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
        "UMU_NO_RUNTIME",
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
_SESSION_BUS_PREFIX = "unix:path="


@dataclass(frozen=True)
class UmuCommand:
    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: Path | None = None
    readable_paths: tuple[Path, ...] = ()


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
        self._runtime_lock = threading.Lock()
        self._prepared_sandbox_runtimes: set[tuple[str, Path]] = set()
        self._termination_lock = threading.Lock()

    @staticmethod
    def _remove_missing_session_bus(environment: dict[str, str]) -> None:
        address = environment.get("DBUS_SESSION_BUS_ADDRESS", "")
        if not address.startswith(_SESSION_BUS_PREFIX) or ";" in address:
            return
        path = address.removeprefix(_SESSION_BUS_PREFIX).split(",", 1)[0]
        if path and not Path(path).exists():
            environment.pop("DBUS_SESSION_BUS_ADDRESS", None)

    @staticmethod
    def _absolute_path(path: Path) -> Path:
        return path.expanduser().resolve(strict=False)

    def _sandbox_proton(
        self, game: UmuGame, proton: str
    ) -> tuple[str, tuple[Path, ...]]:
        if not game.sandbox or not (
            "FLATPAK_ID" in self.base_environment
            or self.base_environment.get("container") == "flatpak"
            or "FLATPAK_ID" in os.environ
        ):
            return proton, ()

        source = Path(proton).expanduser()
        if not source.is_absolute() or not source.is_dir():
            raise UmuProcessError(
                "Dedicated Flatpak sandboxes require an installed Proton version"
            )
        source = source.resolve()
        if source == Path(source.anchor):
            raise UmuProcessError(
                "Dedicated Flatpak sandboxes cannot use the filesystem root as Proton"
            )
        manifest_path = source / "toolmanifest.vdf"
        try:
            manifest_data = manifest_path.read_bytes()
            manifest = vdf.loads(manifest_data.decode("utf-8", errors="replace"))
            properties = manifest["manifest"]
            if not isinstance(properties, dict):
                raise TypeError
        except (KeyError, OSError, SyntaxError, TypeError, ValueError) as error:
            raise UmuProcessError("The selected Proton manifest is invalid") from error

        if "require_tool_appid" not in properties:
            return str(source), (source,)
        while "require_tool_appid" in properties:
            properties.pop("require_tool_appid")

        digest = sha256(f"{source}\0".encode() + manifest_data).hexdigest()[:20]
        shadow = self.data_root / "sandbox-tools" / digest
        shadow.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            if child.name == "toolmanifest.vdf":
                continue
            target = shadow / child.name
            if target.is_symlink():
                if target.resolve(strict=False) != child.resolve(strict=False):
                    raise UmuProcessError("The Proton sandbox cache is invalid")
                continue
            if target.exists():
                raise UmuProcessError("The Proton sandbox cache is invalid")
            target.symlink_to(child, target_is_directory=child.is_dir())
        shadow_manifest = shadow / "toolmanifest.vdf"
        temporary_manifest = (
            shadow / f".toolmanifest-{os.getpid()}-{threading.get_ident()}"
        )
        temporary_manifest.write_text(
            vdf.dumps(manifest, pretty=True),
            encoding="utf-8",
        )
        temporary_manifest.replace(shadow_manifest)
        return str(shadow), (source,)

    def _environment(
        self, game: UmuGame, *, prefix_only: bool
    ) -> tuple[dict[str, str], tuple[Path, ...]]:
        overridden = RESERVED_ENVIRONMENT_KEYS.intersection(game.environment)
        if overridden:
            names = ", ".join(sorted(overridden))
            raise ReservedEnvironmentError(
                f"Reserved UMU environment variables cannot be overridden: {names}"
            )

        prefix = game.prefix.resolve(self.data_root)
        environment = self.base_environment.copy()
        self._remove_missing_session_bus(environment)
        for key in RESERVED_ENVIRONMENT_KEYS:
            environment.pop(key, None)
        environment.update(game.environment)
        resolved_proton = self.proton_resolver(game.proton)
        runner = Path(resolved_proton).name
        proton, readable_paths = self._sandbox_proton(game, resolved_proton)
        environment.update(
            {
                "GAMEID": game.game_id,
                "PROTONPATH": proton,
                "STORE": game.store,
                "WINEPREFIX": str(prefix),
            }
        )
        if readable_paths:
            environment["UMU_NO_RUNTIME"] = "1"
        if not prefix_only:
            if is_v2_runner(runner):
                profile = AdaptiveLaunchProfile.from_root(
                    prefix,
                    runner,
                    str(self._absolute_path(game.executable)),
                )
                profile.prepare()
                if profile.trace_dir is not None:
                    environment[TRACE_ENV] = str(profile.trace_dir)
            install_path = (
                self._absolute_path(game.working_directory)
                if game.working_directory
                else self._absolute_path(game.executable).parent
            )
            environment["STEAM_COMPAT_INSTALL_PATH"] = str(install_path)
        else:
            environment.pop("STEAM_COMPAT_INSTALL_PATH", None)
        return environment, readable_paths

    def prepare(self, game: UmuGame) -> UmuCommand:
        executable = self._absolute_path(game.executable)
        cwd = (
            self._absolute_path(game.working_directory)
            if game.working_directory
            else None
        )
        environment, readable_paths = self._environment(game, prefix_only=False)
        return UmuCommand(
            argv=(
                str(self.installation.path),
                str(executable),
                *game.arguments,
            ),
            env=environment,
            cwd=cwd,
            readable_paths=readable_paths,
        )

    def prepare_prefix(self, game: UmuGame) -> UmuCommand:
        environment, readable_paths = self._environment(game, prefix_only=True)
        return UmuCommand(
            argv=(str(self.installation.path), ""),
            env=environment,
            readable_paths=readable_paths,
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
        environment, readable_paths = self._environment(game, prefix_only=True)
        return UmuCommand(
            argv=(str(self.installation.path), "winetricks", *validated),
            env=environment,
            readable_paths=readable_paths,
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

    @staticmethod
    def _runtime_root(environment: Mapping[str, str]) -> Path:
        if folders_path := environment.get("UMU_FOLDERS_PATH"):
            data_home = Path(folders_path)
        else:
            home = Path(environment.get("HOME", str(Path.home())))
            if environment.get("container") == "flatpak":
                data_home = Path(
                    environment.get(
                        "HOST_XDG_DATA_HOME", home.joinpath(".local", "share")
                    )
                )
            else:
                data_home = Path(
                    environment.get("XDG_DATA_HOME", home.joinpath(".local", "share"))
                )
        return data_home.expanduser().absolute().joinpath("umu")

    def _ensure_sandbox_runtime(self, command: UmuCommand) -> None:
        proton = command.env["PROTONPATH"]
        runtime = self._runtime_root(command.env)
        runtime_key = (proton, runtime)
        with self._runtime_lock:
            if runtime_key in self._prepared_sandbox_runtimes:
                return

            runtime.mkdir(parents=True, exist_ok=True)
            marker = runtime.joinpath(
                f".bottles-runtime-{os.getpid()}-{time.monotonic_ns()}"
            )
            environment = command.env.copy()
            environment["UMU_NO_PROTON"] = "1"
            process = subprocess.Popen(
                [str(self.installation.path), "/usr/bin/touch", str(marker)],
                env=environment,
                shell=False,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            if process.stdout is not None:
                for line in process.stdout:
                    try:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    except (OSError, UnicodeError):
                        pass
            return_code = process.wait()
            runtime_ready = marker.is_file()
            marker.unlink(missing_ok=True)
            if return_code or not runtime_ready:
                raise UmuProcessError("UMU runtime setup failed")
            self._prepared_sandbox_runtimes.add(runtime_key)

    def _start(self, game: UmuGame, command: UmuCommand) -> subprocess.Popen[str]:
        sandbox = self._sandbox_manager(game, command) if game.sandbox else None
        if sandbox is not None:
            self._ensure_sandbox_runtime(command)
        with self._process_lock:
            running = self._processes.get(game.id)
            if running is not None:
                if self._group_exists(running):
                    raise UmuProcessError(f"UMU game is already running: {game.id}")
                del self._processes[game.id]
            if prefix_has_process(game.prefix.resolve(self.data_root)):
                raise UmuProcessError(f"The UMU prefix is already in use: {game.id}")
            argv: list[str] | str = list(command.argv)
            shell = False
            if sandbox is not None:
                argv = sandbox.get_cmd(shlex.join(command.argv))
                shell = True
            process = subprocess.Popen(
                argv,
                cwd=str(command.cwd) if command.cwd is not None else None,
                env=command.env.copy(),
                shell=shell,
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

    def _sandbox_manager(self, game: UmuGame, command: UmuCommand) -> SandboxManager:
        prefix = game.prefix.resolve(self.data_root)
        prefix.mkdir(parents=True, exist_ok=True)

        runtime = self._runtime_root(command.env)
        runtime.mkdir(parents=True, exist_ok=True)

        sandbox_cwd = (command.cwd or prefix).resolve(strict=False)
        required_writable_paths = (prefix, sandbox_cwd)
        if any(path == Path(path.anchor) for path in required_writable_paths):
            raise UmuProcessError(
                "Dedicated sandbox paths cannot use the filesystem root"
            )

        writable_paths = set(required_writable_paths)
        cache_home_value = self.base_environment.get("XDG_CACHE_HOME")
        if cache_home_value is None and (home := self.base_environment.get("HOME")):
            cache_home_value = str(Path(home).joinpath(".cache"))
        if cache_home_value:
            cache_home = self._absolute_path(Path(cache_home_value))
            if cache_home != Path(cache_home.anchor):
                cache_home.mkdir(parents=True, exist_ok=True)
                writable_paths.add(cache_home)

        executable_directory = self._absolute_path(game.executable).parent
        if (
            executable_directory != Path(executable_directory.anchor)
            and executable_directory.is_dir()
        ):
            writable_paths.add(executable_directory)

        readable_paths = {*command.readable_paths, runtime}
        proton_path = Path(command.env["PROTONPATH"]).expanduser()
        if proton_path.is_absolute():
            proton_path = proton_path.resolve(strict=False)
            if proton_path == Path(proton_path.anchor):
                raise UmuProcessError(
                    "The UMU Proton path cannot use the filesystem root"
                )
            if proton_path.is_dir():
                readable_paths.add(proton_path)

        return SandboxManager(
            envs=command.env,
            chdir=str(sandbox_cwd),
            clear_env=True,
            share_paths_ro=[str(path) for path in sorted(readable_paths)],
            share_paths_rw=[str(path) for path in sorted(writable_paths)],
            share_net=game.share_net,
            share_host_ro=False,
        )

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
