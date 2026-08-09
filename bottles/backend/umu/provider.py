import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bottles.backend.globals import Paths

UmuProviderSource = Literal["explicit", "system", "bundled", "managed"]
_VERSION_PATTERN = re.compile(r"\bumu-launcher\s+version\s+([^\s(]+)", re.IGNORECASE)


class UmuProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class UmuInstallation:
    path: Path
    version: str
    source: UmuProviderSource


class UmuProvider:
    def __init__(
        self,
        explicit_path: str | Path | None = None,
        bundled_path: str | Path | None = "/app/bin/umu-run",
        fallback_path: str | Path | None = None,
        timeout: float = 5,
    ):
        self.explicit_path = Path(explicit_path).expanduser() if explicit_path else None
        self.bundled_path = Path(bundled_path).expanduser() if bundled_path else None
        self.fallback_path = (
            Path(fallback_path).expanduser()
            if fallback_path
            else Path(Paths.base).joinpath("umu", "launcher", "umu-run")
        )
        if timeout <= 0:
            raise ValueError("UMU provider timeout must be positive")
        self.timeout = timeout

    def _inspect(self, path: Path, source: UmuProviderSource) -> UmuInstallation:
        try:
            resolved = path.expanduser().resolve(strict=True)
        except OSError as error:
            raise UmuProviderError(f"UMU launcher does not exist: {path}") from error
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise UmuProviderError(f"UMU launcher is not executable: {path}")
        try:
            result = subprocess.run(
                [str(resolved), "--version"],
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UmuProviderError(f"Cannot inspect UMU launcher: {path}") from error

        output = f"{result.stdout}\n{result.stderr}"
        match = _VERSION_PATTERN.search(output)
        if result.returncode != 0 or match is None:
            raise UmuProviderError(f"Invalid UMU launcher: {path}")
        return UmuInstallation(path=resolved, version=match.group(1), source=source)

    def resolve(self) -> UmuInstallation:
        if self.explicit_path is not None:
            return self._inspect(self.explicit_path, "explicit")

        candidates: list[tuple[Path, UmuProviderSource]] = []
        if system_path := shutil.which("umu-run"):
            system = Path(system_path)
            normalized = system.expanduser().resolve(strict=False)
            if (
                self.bundled_path is not None
                and normalized == self.bundled_path.resolve(strict=False)
            ):
                source: UmuProviderSource = "bundled"
            elif normalized == self.fallback_path.resolve(strict=False):
                source = "managed"
            else:
                source = "system"
            candidates.append((system, source))
        if self.bundled_path is not None:
            candidates.append((self.bundled_path, "bundled"))
        candidates.append((self.fallback_path, "managed"))

        failures = []
        visited = set()
        for path, source in candidates:
            normalized = path.expanduser().resolve(strict=False)
            if normalized in visited:
                continue
            visited.add(normalized)
            try:
                return self._inspect(path.expanduser(), source)
            except UmuProviderError as error:
                failures.append(str(error))

        detail = "; ".join(failures) if failures else "no candidates found"
        raise UmuProviderError(f"No usable UMU launcher found: {detail}")
