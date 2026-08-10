import hashlib
import os
import re
from pathlib import Path

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()

PROFILE_ENV = "SODA_ADAPTIVE_PROFILE"
_MAX_PROFILE_SIZE = 4 * 1024 * 1024
_MAX_FILES = 512
_MAX_PREFETCH_SIZE = 1024 * 1024 * 1024
_MINIMUM_SODA_VERSION = (11, 0, 5)


def is_supported_runner(runner: str) -> bool:
    match = re.match(
        r"^soda-(\d+)\.(\d+)-(\d+)(?:-|$)", runner or "", re.IGNORECASE
    )
    if not match:
        return False
    return tuple(map(int, match.groups())) >= _MINIMUM_SODA_VERSION


class AdaptiveLaunchProfile:
    def __init__(self, config: BottleConfig, executable: str):
        identity = os.path.realpath(executable)
        digest = hashlib.sha256(os.fsencode(identity)).hexdigest()[:20]
        bottle = ManagerUtils.get_bottle_path(config)
        self.path = Path(bottle) / ".adaptive-launch" / f"{digest}.profile"

    def prepare(self) -> int:
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.touch(mode=0o600)
                return 0
        except OSError as error:
            logging.warning(f"Unable to create adaptive launch profile: {error}")
            return 0

        try:
            data = self.path.read_bytes()
        except OSError as error:
            logging.warning(f"Unable to read adaptive launch profile: {error}")
            return 0

        if len(data) > _MAX_PROFILE_SIZE:
            data = data[-_MAX_PROFILE_SIZE:]
            data = data[data.find(b"\0") + 1 :]

        paths = []
        total_size = 0
        for raw_path in reversed(data.split(b"\0")):
            if not raw_path:
                continue
            try:
                path = os.fsdecode(raw_path)
                stat = os.stat(path)
            except (OSError, ValueError):
                continue
            if not os.path.isfile(path) or path in paths:
                continue
            if total_size + stat.st_size > _MAX_PREFETCH_SIZE:
                continue
            paths.append(path)
            total_size += stat.st_size
            if len(paths) == _MAX_FILES:
                break

        paths.reverse()
        try:
            self.path.write_bytes(
                b"\0".join(os.fsencode(path) for path in paths) + b"\0"
            )
        except OSError as error:
            logging.warning(f"Unable to update adaptive launch profile: {error}")

        if not hasattr(os, "posix_fadvise"):
            return 0

        prepared = 0
        for path in paths:
            try:
                fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
                try:
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_WILLNEED)
                finally:
                    os.close(fd)
            except OSError:
                continue
            prepared += 1
        return prepared
