import shlex
from collections.abc import Iterable
from dataclasses import replace
from gettext import gettext as _
from pathlib import Path
from typing import Callable, Optional

from bottles.backend.globals import Paths
from bottles.backend.models.result import Result
from bottles.backend.umu.executor import UmuExecutor
from bottles.backend.umu.models import UmuGame
from bottles.backend.umu.repository import UmuGameRepository

SUPPORTED_ACTIONS = frozenset({"install_exe", "override_dll"})


class UmuDependencyError(RuntimeError):
    pass


class UmuDependencyInstaller:
    def __init__(
        self,
        manager,
        repository: UmuGameRepository,
        executor: UmuExecutor,
    ):
        self.manager = manager
        self.repository = repository
        self.executor = executor

    def _plan(self, names: Iterable[str], installed: set[str]):
        planned = []
        visiting = set()
        visited = set(installed)

        def visit(name):
            if name in visited:
                return
            if name in visiting:
                raise UmuDependencyError(f"Cyclic dependency chain for {name}")
            manifest = self.manager.dependency_manager.get_dependency(name)
            if not isinstance(manifest, dict):
                raise UmuDependencyError(f"Cannot find Bottles dependency {name}")
            dependencies = manifest.get("Dependencies", [])
            steps = manifest.get("Steps")
            if not isinstance(dependencies, list) or not isinstance(steps, list):
                raise UmuDependencyError(f"Invalid Bottles dependency {name}")

            visiting.add(name)
            for dependency in dependencies:
                if not isinstance(dependency, str):
                    raise UmuDependencyError(f"Invalid dependency chain for {name}")
                visit(dependency)

            for step in steps:
                if (
                    not isinstance(step, dict)
                    or step.get("action") not in SUPPORTED_ACTIONS
                ):
                    action = (
                        step.get("action", "unknown")
                        if isinstance(step, dict)
                        else "unknown"
                    )
                    raise UmuDependencyError(
                        f"Bottles dependency {name} uses unsupported UMU action "
                        f"{action}"
                    )
                self._validate_step(name, step)

            visiting.remove(name)
            visited.add(name)
            planned.append((name, manifest))

        for name in names:
            if not isinstance(name, str) or not name:
                raise UmuDependencyError("Invalid Bottles dependency name")
            visit(name)
        return planned

    def is_compatible(self, name: str, installed: Iterable[str] = ()) -> bool:
        try:
            self._plan((name,), set(installed))
        except (OSError, ValueError, UmuDependencyError):
            return False
        return True

    def _validate_step(self, dependency, step):
        if step["action"] == "install_exe":
            url = step.get("url")
            file_name = step.get("file_name")
            if not isinstance(url, str) or not isinstance(file_name, str):
                raise UmuDependencyError(
                    f"Bottles dependency {dependency} has an invalid download"
                )
            if url.startswith("temp/"):
                raise UmuDependencyError(
                    f"Bottles dependency {dependency} uses a temporary source"
                )
            self._arguments(step.get("arguments"))
            if not isinstance(step.get("environment", {}), dict):
                raise UmuDependencyError(
                    f"Bottles dependency {dependency} has an invalid environment"
                )
            return

        if step.get("url"):
            raise UmuDependencyError(
                f"Bottles dependency {dependency} uses a dynamic DLL override"
            )
        self._apply_override({}, step)

    @staticmethod
    def _arguments(value):
        if value in (None, ""):
            return ()
        values = value if isinstance(value, list) else [value]
        arguments = []
        for item in values:
            if not isinstance(item, str):
                raise UmuDependencyError("Invalid dependency arguments")
            arguments.extend(shlex.split(item))
        return tuple(arguments)

    @staticmethod
    def _apply_override(environment, step):
        overrides = []
        if step.get("bundle"):
            for item in step["bundle"]:
                if not isinstance(item, dict):
                    raise UmuDependencyError("Invalid DLL override")
                overrides.append((item.get("value"), item.get("data")))
        else:
            overrides.append((step.get("dll"), step.get("type")))

        value = environment.get("WINEDLLOVERRIDES", "").strip(";")
        parts = [value] if value else []
        for name, mode in overrides:
            if not isinstance(name, str) or not isinstance(mode, str):
                raise UmuDependencyError("Invalid DLL override")
            parts.append(f"{name}={mode}")
        environment["WINEDLLOVERRIDES"] = ";".join(parts)

    def _install_executable(
        self,
        game,
        step,
        progress_cb: Optional[Callable[[str], None]] = None,
        progress_progress_cb: Optional[Callable[[Optional[float]], None]] = None,
    ):
        url = step.get("url")
        file_name = step.get("file_name")
        rename = step.get("rename", "")
        if not isinstance(url, str) or not isinstance(file_name, str):
            raise UmuDependencyError("Invalid dependency download")
        if url.startswith("temp/"):
            raise UmuDependencyError("Temporary dependency sources are not supported")

        if progress_cb:
            progress_cb(_("Downloading {0}...").format(rename or file_name))

        def update_progress(received=0, total=0, _status=None):
            if progress_progress_cb:
                progress_progress_cb(received / total if total else None)

        result = self.manager.component_manager.download(
            download_url=url,
            file=file_name,
            rename=rename,
            checksum=step.get("file_checksum", ""),
            func=update_progress,
        )
        if progress_progress_cb:
            progress_progress_cb(None)
        if not result.ok:
            raise UmuDependencyError(f"Cannot download {file_name}")

        executable = Path(Paths.temp) / (rename or file_name)
        if not executable.is_file():
            raise UmuDependencyError(
                f"Downloaded dependency is missing: {executable.name}"
            )

        step_environment = step.get("environment", {})
        if not isinstance(step_environment, dict):
            raise UmuDependencyError("Invalid dependency environment")
        installer = replace(
            game,
            executable=executable,
            arguments=self._arguments(step.get("arguments")),
            working_directory=Path(Paths.temp),
            environment={**game.environment, **step_environment},
        )
        if progress_cb:
            progress_cb(_("Running {0}...").format(executable.name))
        self.executor.run(installer)
        return_code = self.executor.wait(installer)
        if return_code not in (0, 194):
            raise UmuDependencyError(
                f"Dependency installer exited with status {return_code}"
            )

    def install(
        self,
        game: UmuGame,
        names: Iterable[str],
        progress_cb: Optional[Callable[[str], None]] = None,
        progress_progress_cb: Optional[Callable[[Optional[float]], None]] = None,
    ) -> Result:
        updated = game
        try:
            if isinstance(names, (str, bytes)):
                raise UmuDependencyError("Invalid Bottles dependency list")
            installed_values = game.extra.get("installed_dependencies", [])
            if not isinstance(installed_values, list) or not all(
                isinstance(name, str) for name in installed_values
            ):
                raise UmuDependencyError("Invalid installed dependency metadata")
            installed = set(installed_values)
            plan = self._plan(names, installed)
            environment = dict(game.environment)
            completed = list(installed)
            for name, manifest in plan:
                if progress_cb:
                    progress_cb(_('Installing "{0}"...').format(name))
                for step in manifest["Steps"]:
                    if step["action"] == "install_exe":
                        current = replace(updated, environment=environment)
                        self._install_executable(
                            current,
                            step,
                            progress_cb=progress_cb,
                            progress_progress_cb=progress_progress_cb,
                        )
                    else:
                        if progress_cb:
                            progress_cb(_("Updating DLL overrides..."))
                        self._apply_override(environment, step)
                completed.append(name)
                updated = self.repository.update(
                    updated,
                    environment=environment,
                    extra={
                        **updated.extra,
                        "installed_dependencies": sorted(set(completed)),
                    },
                )
            if progress_cb:
                progress_cb(_("Finalizing installation..."))
        except (OSError, ValueError, UmuDependencyError) as error:
            return Result(False, data=updated, message=str(error))
        return Result(True, data=updated)
