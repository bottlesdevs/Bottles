import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
from pathlib import Path

from bottles.backend.logger import Logger
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()

PROFILE_ENV = "SODA_ADAPTIVE_PROFILE"
TRACE_ENV = "SODA_ADAPTIVE_TRACE_DIR"
_TRACE_HEADER = b"SODAAL2\0"
_MAX_PROFILE_SIZE = 4 * 1024 * 1024
_MAX_FILES = 512
_MAX_SESSIONS = 5
_MAX_TRACE_DIRS = 32
_MAX_PREFETCH_SIZE = 1024 * 1024 * 1024
_TRACE_GRACE_SECONDS = 60
_MINIMUM_SODA_VERSION = (11, 0, 5)
_MINIMUM_V2_VERSION = (11, 0, 7)


def _runner_version(runner: str):
    match = re.match(r"^soda-(\d+)\.(\d+)-(\d+)(?:-|$)", runner or "", re.IGNORECASE)
    if not match:
        return None
    return tuple(map(int, match.groups()))


def is_supported_runner(runner: str) -> bool:
    version = _runner_version(runner)
    return version is not None and version >= _MINIMUM_SODA_VERSION


def is_v2_runner(runner: str) -> bool:
    version = _runner_version(runner)
    return version is not None and version >= _MINIMUM_V2_VERSION


def _open_regular(path: Path):
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode):
            return fd, info
    except OSError:
        os.close(fd)
        raise
    os.close(fd)
    raise OSError(f"Not a regular file: {path}")


def _read_regular(path: Path, limit: int):
    try:
        fd, info = _open_regular(path)
    except OSError:
        return None
    try:
        if info.st_size > limit:
            return None
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        return data if len(data) <= limit else None
    except OSError:
        return None
    finally:
        os.close(fd)


def _write_atomic(path: Path, data: bytes) -> bool:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    fd = -1
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("Unable to write adaptive launch profile")
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(temporary, path)
        return True
    except OSError as error:
        logging.warning(f"Unable to update adaptive launch profile: {error}")
        return False
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _prefetch_budget() -> int:
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        available = pages * page_size
        if available > 0:
            return min(_MAX_PREFETCH_SIZE, available // 8)
    except (OSError, TypeError, ValueError):
        pass
    return _MAX_PREFETCH_SIZE


def _select_paths(paths):
    selected = []
    total_size = 0
    budget = _prefetch_budget()
    for path in paths:
        if path in selected:
            continue
        try:
            fd, info = _open_regular(Path(path))
            os.close(fd)
        except (OSError, ValueError):
            continue
        if total_size + info.st_size > budget:
            continue
        selected.append(path)
        total_size += info.st_size
        if len(selected) == _MAX_FILES:
            break
    return selected


def _prefetch(paths) -> int:
    if not hasattr(os, "posix_fadvise"):
        return 0
    prepared = 0
    for path in paths:
        try:
            fd, _info = _open_regular(Path(path))
            try:
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_WILLNEED)
            finally:
                os.close(fd)
        except OSError:
            continue
        prepared += 1
    return prepared


class AdaptiveLaunchProfile:
    def __init__(self, config: BottleConfig, executable: str):
        identity = os.path.realpath(executable)
        bottle = Path(ManagerUtils.get_bottle_path(config))
        legacy_digest = hashlib.sha256(os.fsencode(identity)).hexdigest()[:20]
        self.legacy_path = bottle / ".adaptive-launch" / f"{legacy_digest}.profile"
        self.runner = config.Runner
        self.v2 = is_v2_runner(self.runner)
        self.trace_dir = None

        if not self.v2:
            self.path = self.legacy_path
            return

        identity = f"{identity}\0{self.runner}"
        digest = hashlib.sha256(os.fsencode(identity)).hexdigest()[:20]
        self.root = bottle / ".adaptive-launch" / "v2" / digest
        self.path = self.root / "profile.json"
        self.traces = self.root / "traces"

    def prepare(self) -> int:
        if not self.v2:
            return self._prepare_legacy()
        return self._prepare_v2()

    def _prepare_legacy(self) -> int:
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as error:
            logging.warning(f"Unable to create adaptive launch profile: {error}")
            return 0

        data = _read_regular(self.path, _MAX_PROFILE_SIZE)
        if data is None:
            if not os.path.lexists(self.path):
                _write_atomic(self.path, b"")
            return 0

        paths = []
        for raw_path in reversed(data.split(b"\0")):
            if not raw_path:
                continue
            try:
                path = os.fsdecode(raw_path)
            except ValueError:
                continue
            if path not in paths:
                paths.append(path)

        paths = _select_paths(paths)
        paths.reverse()
        _write_atomic(
            self.path,
            b"\0".join(os.fsencode(path) for path in paths) + (b"\0" if paths else b""),
        )
        return _prefetch(paths)

    def _prepare_v2(self) -> int:
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.traces.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            logging.warning(f"Unable to create adaptive launch profile: {error}")
            return 0

        profile = self._load_profile()
        changed = False
        if not profile["legacy_migrated"]:
            legacy = self._legacy_session()
            if legacy:
                profile["sessions"].append({"created": 0, "paths": legacy})
            profile["legacy_migrated"] = True
            changed = True

        sessions, consumed = self._collect_traces()
        if sessions:
            profile["sessions"].extend(sessions)
            changed = True
        if consumed:
            changed = True
        profile["sessions"] = profile["sessions"][-_MAX_SESSIONS:]

        paths = _select_paths(self._rank_paths(profile["sessions"]))
        if changed and self._save_profile(profile):
            self._remove_traces(consumed)

        try:
            self.trace_dir = self.traces / uuid.uuid4().hex
            self.trace_dir.mkdir(mode=0o700)
        except OSError as error:
            self.trace_dir = None
            logging.warning(f"Unable to create adaptive launch trace: {error}")

        return _prefetch(paths)

    def _load_profile(self):
        empty = {
            "version": 2,
            "runner": self.runner,
            "legacy_migrated": False,
            "sessions": [],
        }
        data = _read_regular(self.path, _MAX_PROFILE_SIZE)
        if data is None:
            return empty
        try:
            profile = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return empty
        if (
            not isinstance(profile, dict)
            or profile.get("version") != 2
            or profile.get("runner") != self.runner
            or not isinstance(profile.get("legacy_migrated"), bool)
            or not isinstance(profile.get("sessions"), list)
        ):
            return empty

        sessions = []
        for session in profile["sessions"][-_MAX_SESSIONS:]:
            if not isinstance(session, dict) or not isinstance(
                session.get("paths"), list
            ):
                continue
            paths = [path for path in session["paths"] if isinstance(path, str)]
            sessions.append(
                {"created": session.get("created", 0), "paths": paths[:_MAX_FILES]}
            )
        profile["sessions"] = sessions
        return profile

    def _legacy_session(self):
        data = _read_regular(self.legacy_path, _MAX_PROFILE_SIZE)
        if data is None:
            return []
        paths = []
        for raw_path in data.split(b"\0"):
            if not raw_path:
                continue
            try:
                path = os.fsdecode(raw_path)
            except ValueError:
                continue
            if os.path.isabs(path) and path not in paths:
                paths.append(path)
            if len(paths) == _MAX_FILES:
                break
        return paths

    def _collect_traces(self):
        cutoff = time.time() - _TRACE_GRACE_SECONDS
        candidates = []
        try:
            entries = list(self.traces.iterdir())
        except OSError:
            return [], []
        for path in entries:
            try:
                info = path.lstat()
            except OSError:
                continue
            if stat.S_ISDIR(info.st_mode) and info.st_mtime <= cutoff:
                candidates.append((info.st_mtime, path))

        sessions = []
        consumed = []
        for _created, directory in sorted(candidates)[:_MAX_TRACE_DIRS]:
            session = self._read_trace_directory(directory, cutoff)
            if session is None:
                continue
            paths, created = session
            if paths:
                sessions.append({"created": created, "paths": paths})
            consumed.append(directory)
        return sessions, consumed

    @staticmethod
    def _read_trace_directory(directory: Path, cutoff: float):
        try:
            entries = list(directory.iterdir())
        except OSError:
            return None

        files = []
        created = 0
        for path in entries:
            try:
                info = path.lstat()
            except OSError:
                return None
            if info.st_mtime > cutoff:
                return None
            files.append((info.st_mtime, path))
            created = max(created, int(info.st_mtime))

        paths = []
        for _modified, path in sorted(files):
            data = _read_regular(path, _MAX_PROFILE_SIZE)
            if data is None or not data.startswith(_TRACE_HEADER):
                continue
            for raw_path in data[len(_TRACE_HEADER) :].split(b"\0"):
                if not raw_path:
                    continue
                try:
                    decoded = os.fsdecode(raw_path)
                except ValueError:
                    continue
                if os.path.isabs(decoded) and decoded not in paths:
                    paths.append(decoded)
                if len(paths) == _MAX_FILES:
                    break
            if len(paths) == _MAX_FILES:
                break
        return paths, created

    @staticmethod
    def _rank_paths(sessions):
        ranking = {}
        for session_index, session in enumerate(sessions):
            seen = set()
            for position, path in enumerate(session["paths"]):
                if path in seen:
                    continue
                seen.add(path)
                count, position_sum, _last_seen = ranking.get(path, (0, 0, 0))
                ranking[path] = (
                    count + 1,
                    position_sum + position,
                    session_index,
                )
        return sorted(
            ranking,
            key=lambda path: (
                -ranking[path][0],
                ranking[path][1] / ranking[path][0],
                -ranking[path][2],
                path,
            ),
        )

    def _save_profile(self, profile) -> bool:
        while True:
            data = json.dumps(
                profile, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            ).encode()
            if len(data) <= _MAX_PROFILE_SIZE:
                return _write_atomic(self.path, data)
            if len(profile["sessions"]) > 1:
                profile["sessions"].pop(0)
                continue
            if profile["sessions"] and profile["sessions"][0]["paths"]:
                profile["sessions"][0]["paths"].pop()
                continue
            logging.warning(
                "Unable to update adaptive launch profile: profile too large"
            )
            return False

    @staticmethod
    def _remove_traces(directories) -> None:
        for directory in directories:
            try:
                shutil.rmtree(directory)
            except OSError as error:
                logging.warning(f"Unable to remove adaptive launch trace: {error}")
