import os
import pwd
from typing import Optional


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
                return False

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

                relative_target = os.path.relpath(profile_target, users_dir)
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
