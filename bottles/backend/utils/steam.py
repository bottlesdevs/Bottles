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

import os
import shlex
import shutil
from typing import Optional, TextIO

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

        if "1628350" in tool_appid:
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
        dlls = ("libvkd3d-1.dll", "libvkd3d-shader-1.dll")
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
