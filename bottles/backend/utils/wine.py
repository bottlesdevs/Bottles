import ctypes
import errno
import os
import pwd
import secrets
import stat
from typing import Optional


_DIRECTORY_FLAGS = (
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
)
_PREFIX_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_RENAME_NOREPLACE = 1
_LIBC = ctypes.CDLL(None, use_errno=True)
_RENAMEAT2 = _LIBC.renameat2
_RENAMEAT2.argtypes = [
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
]
_RENAMEAT2.restype = ctypes.c_int


def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    result = _RENAMEAT2(
        directory_fd,
        os.fsencode(source),
        directory_fd,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


class WineUtils:
    @staticmethod
    def ensure_user_profile_alias(
        prefix_path: str, username: Optional[str] = None
    ) -> bool:
        if username is None:
            username = os.environ.get("USER")
            if not username:
                try:
                    username = pwd.getpwuid(os.getuid()).pw_name
                except KeyError:
                    username = "wine"

        username = username.rsplit("/", 1)[-1]
        username = username.rsplit("\\", 1)[-1]

        if (
            not username
            or username in {".", ".."}
            or username.casefold() == "public"
            or "\0" in username
        ):
            return False

        users_dir = os.path.join(prefix_path, "drive_c", "users")
        if os.path.lexists(users_dir) and (
            not os.path.isdir(users_dir) or os.path.islink(users_dir)
        ):
            return False

        created_paths = []
        try:
            os.makedirs(users_dir, exist_ok=True)
            users_real = os.path.realpath(users_dir)
            entries = os.listdir(users_dir)
            public_roots = []
            profile_targets = {}

            for entry_name in entries:
                if entry_name.casefold() != "public":
                    continue

                entry = os.path.join(users_dir, entry_name)
                if os.path.islink(entry) or not os.path.isdir(entry):
                    return False

                public_target = os.path.realpath(entry)
                if (
                    public_target == users_real
                    or os.path.commonpath([users_real, public_target]) != users_real
                ):
                    return False
                public_roots.append(public_target)

            for entry_name in entries:
                if entry_name.casefold() == "public":
                    continue

                entry = os.path.join(users_dir, entry_name)
                if not os.path.isdir(entry):
                    if os.path.islink(entry) or entry_name in {username, "steamuser"}:
                        return False
                    continue

                target = os.path.realpath(entry)
                target_stat = os.stat(entry)
                target_identity = (target_stat.st_dev, target_stat.st_ino)
                if (
                    target == users_real
                    or os.path.commonpath([users_real, target]) != users_real
                    or any(
                        os.path.commonpath([public_root, target]) == public_root
                        for public_root in public_roots
                    )
                ):
                    return False
                profile_targets.setdefault(target_identity, target)

            if len(profile_targets) > 1:
                return True

            if profile_targets:
                profile_target = next(iter(profile_targets.values()))
            else:
                profile_target = os.path.join(users_dir, username)
                os.makedirs(profile_target)
                profile_target = os.path.realpath(profile_target)
                created_paths.append(profile_target)

            profile_names = [username]
            if username != "steamuser":
                profile_names.append("steamuser")

            for profile_name in profile_names:
                profile_path = os.path.join(users_dir, profile_name)
                if os.path.lexists(profile_path):
                    if not os.path.isdir(profile_path) or not os.path.samefile(
                        profile_path, profile_target
                    ):
                        raise ValueError
                    continue

                relative_target = os.path.relpath(profile_target, users_real)
                os.symlink(relative_target, profile_path)
                created_paths.append(profile_path)
        except (OSError, ValueError):
            for created_path in reversed(created_paths):
                try:
                    if os.path.islink(created_path):
                        os.unlink(created_path)
                    else:
                        os.rmdir(created_path)
                except OSError:
                    pass
            return False

        return True

    @staticmethod
    def _open_users_directory(prefix_path: str) -> int:
        prefix_fd = os.open(prefix_path, _PREFIX_DIRECTORY_FLAGS)
        try:
            drive_fd = os.open("drive_c", _DIRECTORY_FLAGS, dir_fd=prefix_fd)
            try:
                return os.open("users", _DIRECTORY_FLAGS, dir_fd=drive_fd)
            finally:
                os.close(drive_fd)
        finally:
            os.close(prefix_fd)

    @staticmethod
    def get_user_profile_ids(prefix_path: str):
        users_fd = None
        try:
            users_fd = WineUtils._open_users_directory(prefix_path)
            profiles = set()
            with os.scandir(users_fd) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    entry_stat = entry.stat(follow_symlinks=False)
                    profiles.add((entry_stat.st_dev, entry_stat.st_ino))
            return profiles
        except FileNotFoundError:
            return set()
        except OSError:
            return None
        finally:
            if users_fd is not None:
                os.close(users_fd)

    @staticmethod
    def _replace_directory_links(directory_fd: int) -> bool:
        try:
            with os.scandir(directory_fd) as entries:
                links = [
                    (entry.name, entry.stat(follow_symlinks=False))
                    for entry in entries
                    if entry.is_symlink()
                ]
        except OSError:
            return False

        replaced_all = True
        for link_name, link_stat in links:
            backup_name = None
            backup_fd = None
            for _attempt in range(10):
                candidate = f".bottles-link-{secrets.token_hex(12)}"
                try:
                    backup_fd = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    backup_name = candidate
                    break
                except FileExistsError:
                    continue
                except OSError:
                    break

            if backup_name is None or backup_fd is None:
                replaced_all = False
                continue

            os.close(backup_fd)
            try:
                os.rename(
                    link_name,
                    backup_name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
            except OSError:
                replaced_all = False
                try:
                    os.unlink(backup_name, dir_fd=directory_fd)
                except OSError:
                    pass
                continue

            try:
                moved_stat = os.stat(
                    backup_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if not stat.S_ISLNK(moved_stat.st_mode) or (
                    moved_stat.st_dev,
                    moved_stat.st_ino,
                ) != (link_stat.st_dev, link_stat.st_ino):
                    WineUtils._restore_moved_entry(directory_fd, backup_name, link_name)
                    replaced_all = False
                    continue
            except OSError:
                WineUtils._restore_moved_entry(directory_fd, backup_name, link_name)
                replaced_all = False
                continue

            try:
                os.mkdir(link_name, dir_fd=directory_fd)
            except OSError:
                WineUtils._restore_moved_entry(
                    directory_fd,
                    backup_name,
                    link_name,
                    discard_symlink_on_conflict=True,
                )
                replaced_all = False
                continue

            try:
                os.unlink(backup_name, dir_fd=directory_fd)
            except OSError:
                WineUtils._restore_moved_entry(
                    directory_fd,
                    backup_name,
                    link_name,
                    remove_directory=True,
                    discard_symlink_on_conflict=True,
                )
                replaced_all = False

        return replaced_all

    @staticmethod
    def _restore_moved_entry(
        directory_fd: int,
        backup_name: str,
        entry_name: str,
        remove_directory: bool = False,
        discard_symlink_on_conflict: bool = False,
    ) -> bool:
        if remove_directory:
            try:
                os.rmdir(entry_name, dir_fd=directory_fd)
            except OSError:
                if discard_symlink_on_conflict:
                    try:
                        os.unlink(backup_name, dir_fd=directory_fd)
                    except OSError:
                        pass
                return False

        try:
            _rename_noreplace(directory_fd, backup_name, entry_name)
        except OSError as error:
            if error.errno == errno.EEXIST and discard_symlink_on_conflict:
                try:
                    os.unlink(backup_name, dir_fd=directory_fd)
                except OSError:
                    pass
            return False
        return True

    @staticmethod
    def _open_profile_directory(profile_fd: int, parts: tuple[str, ...]):
        directory_fd = os.dup(profile_fd)
        try:
            for part in parts:
                next_fd = os.open(
                    part,
                    _DIRECTORY_FLAGS,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = next_fd
            return directory_fd
        except OSError as error:
            os.close(directory_fd)
            if error.errno in {errno.ELOOP, errno.ENOENT, errno.ENOTDIR}:
                return None
            raise

    @staticmethod
    def unlink_user_profile_links(prefix_path: str, existing_profiles=None) -> bool:
        if existing_profiles is None:
            existing_profiles = set()

        users_fd = None
        try:
            users_fd = WineUtils._open_users_directory(prefix_path)
            with os.scandir(users_fd) as entries:
                profile_names = [
                    entry.name
                    for entry in entries
                    if not entry.is_symlink() and entry.is_dir(follow_symlinks=False)
                ]

            unlinked_all = True
            for profile_name in profile_names:
                try:
                    profile_fd = os.open(
                        profile_name,
                        _DIRECTORY_FLAGS,
                        dir_fd=users_fd,
                    )
                except OSError:
                    unlinked_all = False
                    continue

                try:
                    profile_stat = os.fstat(profile_fd)
                    profile_id = (profile_stat.st_dev, profile_stat.st_ino)
                    if profile_id in existing_profiles:
                        continue

                    if not WineUtils._replace_directory_links(profile_fd):
                        unlinked_all = False

                    nested_directories = [
                        ("Documents",),
                        ("AppData", "Roaming", "Microsoft", "Windows"),
                    ]
                    for parts in nested_directories:
                        nested_fd = WineUtils._open_profile_directory(profile_fd, parts)
                        if nested_fd is None:
                            continue
                        try:
                            if not WineUtils._replace_directory_links(nested_fd):
                                unlinked_all = False
                        finally:
                            os.close(nested_fd)
                finally:
                    os.close(profile_fd)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        finally:
            if users_fd is not None:
                os.close(users_fd)

        return unlinked_all

    @staticmethod
    def get_user_dir(prefix_path: str):
        usersdir = os.path.join(prefix_path, "drive_c", "users")
        users_real = os.path.realpath(usersdir)
        profiles = []
        profile_targets = set()
        for user_dir in sorted(os.listdir(usersdir)):
            if user_dir.casefold() == "public":
                continue

            profile_path = os.path.join(usersdir, user_dir)
            if not os.path.isdir(profile_path):
                continue

            target = os.path.realpath(profile_path)
            if (
                target == users_real
                or os.path.commonpath([users_real, target]) != users_real
            ):
                raise Exception("Invalid user directory found.")

            target_stat = os.stat(profile_path)
            profile_targets.add((target_stat.st_dev, target_stat.st_ino))
            profiles.append(user_dir)

        if not profiles:
            raise Exception("No user directories found.")
        if len(profile_targets) > 1:
            raise Exception("Multiple user directories found.")

        for user_dir in profiles:
            if not os.path.islink(os.path.join(usersdir, user_dir)):
                return user_dir
        return profiles[0]
