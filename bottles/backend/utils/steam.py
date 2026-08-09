# steam.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
from typing import Optional, TextIO

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.models.vdict import VDFDict
from bottles.backend.utils import vdf

logging = Logger()


class SteamUtils:
    @staticmethod
    def parse_acf(data: str) -> VDFDict:
        """
        Parses an ACF file. Just a wrapper for vdf.loads.
        """
        return vdf.loads(data)

    @staticmethod
    def parse_vdf(data: str) -> VDFDict:
        """
        Parses a VDF file. Just a wrapper for vdf.loads.
        """
        return vdf.loads(data)

    @staticmethod
    def to_vdf(data: VDFDict, fp: TextIO):
        """
        Saves a VDF file. Just a wrapper for vdf.dumps.
        """
        vdf.dump(data, fp, pretty=True)

    @staticmethod
    def is_proton(path: str) -> bool:
        """
        Checks if a directory is a Proton directory.
        """
        toolmanifest = os.path.join(path, "toolmanifest.vdf")
        if not os.path.isfile(toolmanifest):
            return False

        f = open(toolmanifest, "r", errors="replace")
        data = SteamUtils.parse_vdf(f.read())
        compat_layer_name = data.get("manifest", {}).get("compatmanager_layer_name", {})

        commandline = data.get("manifest", {}).get("commandline", {})

        return "proton" in compat_layer_name or "proton" in commandline

    @staticmethod
    def get_associated_runtime(path: str) -> Optional[str]:
        """
        Get the associated runtime of a Proton directory.
        """
        toolmanifest = os.path.join(path, "toolmanifest.vdf")
        if not os.path.isfile(toolmanifest):
            logging.error(f"toolmanifest.vdf not found in Proton directory: {path}")
            return None

        runtime = "scout"
        f = open(toolmanifest, "r", errors="replace")
        data = SteamUtils.parse_vdf(f.read())
        tool_appid = data.get("manifest", {}).get("require_tool_appid", {})

        if "4183110" in tool_appid:
            runtime = "steamrt4"
        elif "1628350" in tool_appid:
            runtime = "sniper"
        elif "1391110" in tool_appid:
            runtime = "soldier"

        return runtime

    @staticmethod
    def get_dist_directory(path: str) -> str:
        """
        Get the sub-directory containing the wine libraries and binaries.
        """
        dist_directory = path
        if os.path.isdir(os.path.join(path, "dist")):
            dist_directory = os.path.join(path, "dist")
        elif os.path.isdir(os.path.join(path, "files")):
            dist_directory = os.path.join(path, "files")
        else:
            logging.warning(
                f"No /dist or /files sub-directory was found under this Proton directory: {path}"
            )

        return dist_directory

    @staticmethod
    def sync_proton_vkd3d(path: str, prefix: str, arch: str) -> None:
        """Sync Proton's WineD3D dependencies into a Bottles prefix."""
        dist_directory = SteamUtils.get_dist_directory(path)
        default_prefix = os.path.join(dist_directory, "share/default_pfx")
        dlls = ("libvkd3d-1.dll", "libvkd3d-shader-1.dll", "libvkd3d-utils-1.dll")
        directories = [("system32", "system32"), ("syswow64", "syswow64")]
        if arch == "win32":
            directories = [("syswow64", "system32")]

        for source_dir, destination_dir in directories:
            source_dir = os.path.join(default_prefix, "drive_c/windows", source_dir)
            destination_dir = os.path.join(prefix, "drive_c/windows", destination_dir)
            for dll in dlls:
                source = os.path.join(source_dir, dll)
                if not os.path.isfile(source):
                    continue

                destination = os.path.join(destination_dir, dll)
                try:
                    if os.path.isfile(destination):
                        source_stat = os.stat(source)
                        destination_stat = os.stat(destination)
                        if (
                            source_stat.st_size == destination_stat.st_size
                            and source_stat.st_mtime_ns == destination_stat.st_mtime_ns
                        ):
                            continue
                    if os.path.islink(destination):
                        os.unlink(destination)
                    os.makedirs(destination_dir, exist_ok=True)
                    shutil.copy2(source, destination)
                except OSError as exc:
                    logging.warning(f"Failed to update {destination}: {exc}")

    @staticmethod
    def prepare_proton_fsr4(
        path: str, prefix: str, env: dict[str, str], sandbox=None
    ) -> bool:
        fsr4 = env.get("PROTON_FSR4_UPGRADE", "")
        fsr4_rdna3 = env.get("PROTON_FSR4_RDNA3_UPGRADE", "")
        if fsr4 in ("", "0") and fsr4_rdna3 in ("", "0"):
            return False

        try:
            runner_path = os.path.realpath(path)
            runners_path = os.path.realpath(Paths.runners)
            managed_runner = (
                runner_path != runners_path
                and os.path.commonpath((runner_path, runners_path)) == runners_path
            )
            protonfixes = os.path.realpath(os.path.join(runner_path, "protonfixes"))
            managed_protonfixes = (
                protonfixes != runner_path
                and os.path.commonpath((protonfixes, runner_path)) == runner_path
            )
        except (OSError, TypeError, ValueError):
            managed_runner = False
            managed_protonfixes = False
        if not managed_runner:
            logging.warning(
                f"Cannot set up Proton FSR4 from an unmanaged runner: {path}"
            )
            return False
        if not managed_protonfixes or not os.path.isdir(protonfixes):
            logging.warning(f"Invalid protonfixes directory in Proton runner: {path}")
            return False

        path = runner_path

        compat_dir = os.path.join(prefix, ".proton")
        try:
            os.makedirs(compat_dir, exist_ok=True)
        except OSError as exc:
            logging.warning(f"Failed to create Proton data directory: {exc}")
            return False

        compat_config = ["mlfg"]
        if fsr4 not in ("", "0"):
            compat_config.append("fsr4")
        if fsr4_rdna3 not in ("", "0"):
            compat_config.append("fsr4rdna3")

        script = """
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
import protonfixes

env = dict(os.environ)
output_keys = {
    "DISABLE_LAYER_MESA_ANTI_LAG",
    "DXIL_SPIRV_CONFIG",
    "FSR4_UPGRADE",
    "MLFG_UPGRADE",
    "WINE_LOADDLL_REPLACE",
    "WINE_UPSCALER_REPLACE",
}
for key in output_keys:
    if key != "DISABLE_LAYER_MESA_ANTI_LAG":
        env.pop(key, None)
protonfixes.setup_upscalers(
    set(sys.argv[4].split(",")), env, sys.argv[2], sys.argv[3]
)
result = {key: env[key] for key in output_keys if key in env}
print("BOTTLES_PROTON_ENV=" + json.dumps(result, sort_keys=True))
"""
        proton_env = {"HOME": compat_dir}
        for key in (
            "ALL_PROXY",
            "DISABLE_LAYER_MESA_ANTI_LAG",
            "ENABLE_LAYER_MESA_ANTI_LAG",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "PROTON_FSR4_RDNA3_UPGRADE",
            "PROTON_FSR4_UPGRADE",
            "SSL_CERT_DIR",
            "SSL_CERT_FILE",
            "all_proxy",
            "http_proxy",
            "https_proxy",
            "no_proxy",
        ):
            if key in env:
                proton_env[key] = env[key]

        command = [
            sys.executable,
            "-I",
            "-c",
            script,
            path,
            compat_dir,
            prefix,
            ",".join(compat_config),
        ]
        try:
            if sandbox is None:
                process = subprocess.Popen(
                    command,
                    cwd=os.path.dirname(os.path.abspath(sys.executable)),
                    env=proton_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            else:
                sandbox.envs = proton_env
                process = sandbox.run(shlex.join(command))
            try:
                stdout_data, _ = process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    process.kill()
                process.communicate()
                raise
            returncode = process.returncode
            stdout = stdout_data.decode("utf-8", "replace")
        except (OSError, subprocess.TimeoutExpired) as exc:
            logging.warning(f"Failed to set up Proton FSR4 support: {exc}")
            return False

        marker = "BOTTLES_PROTON_ENV="
        payload = next(
            (
                line[len(marker) :]
                for line in reversed(stdout.splitlines())
                if line.startswith(marker)
            ),
            "",
        )
        try:
            updates = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            updates = {}
        if not isinstance(updates, dict):
            updates = {}

        replacements = updates.get("WINE_LOADDLL_REPLACE", "") or updates.get(
            "WINE_UPSCALER_REPLACE", ""
        )
        if not isinstance(replacements, str):
            replacements = ""
        if "WINE_LOADDLL_REPLACE" in updates:
            updates.pop("MLFG_UPGRADE", None)
        fsr4_dll = os.path.join(
            prefix, "drive_c", "windows", "system32", "amdxcffx64.dll"
        )
        if (
            returncode != 0
            or updates.get("FSR4_UPGRADE") != "1"
            or "fsr4" not in replacements.split(",")
            or not os.path.isfile(fsr4_dll)
        ):
            logging.warning("Protonfixes did not enable FSR4 support.")
            return False

        allowed = {
            "DISABLE_LAYER_MESA_ANTI_LAG",
            "DXIL_SPIRV_CONFIG",
            "FSR4_UPGRADE",
            "MLFG_UPGRADE",
            "WINE_LOADDLL_REPLACE",
            "WINE_UPSCALER_REPLACE",
        }
        for key, value in updates.items():
            if key not in allowed or not isinstance(value, str):
                continue
            if key in ("WINE_LOADDLL_REPLACE", "WINE_UPSCALER_REPLACE"):
                existing = [item for item in env.get(key, "").split(",") if item]
                for item in value.split(","):
                    if item and item not in existing:
                        existing.append(item)
                value = ",".join(existing)
            env[key] = value

        return True

    @staticmethod
    def handle_launch_options(launch_options: str) -> tuple[str, str, dict[str, str]]:
        """
        Handle launch options. Supports the %command% pattern.
        Return prefix, arguments, and environment variables.
        """
        env_vars = {}
        prefix, args = "", ""
        if "%command%" in launch_options:
            _c = launch_options.split("%command%")
            prefix = _c[0] if len(_c) > 0 else ""
            args = _c[1] if len(_c) > 1 else ""
        else:
            args = launch_options

        try:
            prefix_list = shlex.split(prefix.strip())
        except ValueError:
            prefix_list = prefix.split(shlex.quote(prefix.strip()))

        for p in prefix_list.copy():
            if "=" in p:
                k, v = p.split("=", 1)
                v = shlex.quote(v) if " " in v else v
                env_vars[k] = v
                prefix_list.remove(p)

        prefix = " ".join(prefix_list)
        return prefix, args, env_vars
