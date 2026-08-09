from pathlib import Path

from bottles.backend.utils.proc import ProcUtils


def prefix_has_process(prefix: str | Path) -> bool:
    target = Path(prefix).expanduser().resolve(strict=False)
    for process in ProcUtils.get_procs():
        try:
            environment = process.get_env()
        except (OSError, PermissionError):
            continue
        for variable in environment.split("\0"):
            name, separator, value = variable.partition("=")
            if name != "WINEPREFIX" or not separator or not value:
                continue
            if Path(value).expanduser().resolve(strict=False) == target:
                return True
    return False
