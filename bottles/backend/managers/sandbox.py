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
import signal
import subprocess
from typing import Optional


class SandboxManager:
    # Track the flatpak-spawn launcher processes per WINEPREFIX so they can be
    # stopped later. Under `flatpak-spawn --sandbox` the wine processes run in a
    # separate sandbox instance the host cannot see by scanning /proc, so the
    # only reliable way to stop them is to kill the launcher process group
    # (combined with --watch-bus, which makes the sandboxed command exit when
    # its launcher goes away).
    _running: dict[str, list[subprocess.Popen]] = {}
    def __init__(
        self,
        envs: Optional[dict] = None,
        chdir: Optional[str] = None,
        clear_env: bool = False,
        share_paths_ro: Optional[list] = None,
        share_paths_rw: Optional[list] = None,
        share_net: bool = False,
        share_user: bool = False,
        share_host_ro: bool = True,
        share_display: bool = True,
        share_sound: bool = True,
        share_gpu: bool = True,
    ):
        self.envs = envs
        self.chdir = chdir
        self.clear_env = clear_env
        self.share_paths_ro = list(share_paths_ro or [])
        self.share_paths_rw = list(share_paths_rw or [])
        self.share_net = share_net
        self.share_user = share_user
        self.share_host_ro = share_host_ro
        self.share_display = share_display
        self.share_sound = share_sound
        self.share_gpu = share_gpu
        self.__uid = os.environ.get("UID", "1000")

    def __get_bwrap(self, cmd: str):
        _cmd = ["bwrap"]

        if self.envs:
            _cmd += [f"--setenv {k} {shlex.quote(v)}" for k, v in self.envs.items()]

        if self.share_host_ro:
            _cmd.append("--ro-bind / /")

        if self.chdir:
            _cmd.append(f"--chdir {shlex.quote(self.chdir)}")
            _cmd.append(f"--bind {shlex.quote(self.chdir)} {shlex.quote(self.chdir)}")

        if self.clear_env:
            _cmd.append("--clearenv")

        if self.share_paths_ro:
            _cmd += [
                f"--ro-bind {shlex.quote(p)} {shlex.quote(p)}"
                for p in self.share_paths_ro
            ]

        if self.share_paths_rw:
            _cmd += [
                f"--bind {shlex.quote(p)} {shlex.quote(p)}" for p in self.share_paths_rw
            ]

        if self.share_sound:
            _cmd.append(
                f"--ro-bind /run/user/{self.__uid}/pulse /run/user/{self.__uid}/pulse"
            )

        if self.share_gpu:
            pass  # not implemented yet

        if self.share_display:
            _cmd.append("--dev-bind /dev/video0 /dev/video0")

        _cmd.append("--share-net" if self.share_net else "--unshare-net")
        _cmd.append("--share-user" if self.share_user else "--unshare-user")
        _cmd.append(cmd)

        return _cmd

    def __get_flatpak_spawn(self, cmd: str):
        _cmd = ["flatpak-spawn", "--sandbox", "--watch-bus"]

        if self.envs:
            _cmd += [f"--env={k}={shlex.quote(v)}" for k, v in self.envs.items()]

        if self.clear_env:
            _cmd.append("--clear-env")

        if self.chdir:
            quoted_dir = shlex.quote(self.chdir)
            _cmd.append(f"--directory={quoted_dir}")
            _cmd.append(f"--sandbox-expose-path={quoted_dir}")

        if self.share_host_ro:
            _cmd.append("--sandbox-expose-path-ro=/")

        if self.share_paths_ro:
            _cmd += [
                f"--sandbox-expose-path-ro={shlex.quote(p)}"
                for p in self.share_paths_ro
            ]

        if self.share_paths_rw:
            _cmd += [
                f"--sandbox-expose-path={shlex.quote(p)}" for p in self.share_paths_rw
            ]

        if not self.share_net:
            _cmd.append("--no-network")

        if self.share_display:
            _cmd.append("--sandbox-flag=share-display")

        if self.share_sound:
            _cmd.append("--sandbox-flag=share-sound")

        if self.share_gpu:
            _cmd.append("--sandbox-flag=share-gpu")

        _cmd.append(cmd)

        return _cmd

    def get_cmd(self, cmd: str):
        if "FLATPAK_ID" in os.environ:
            _cmd = self.__get_flatpak_spawn(cmd)
        else:
            _cmd = self.__get_bwrap(cmd)

        return " ".join(_cmd)

    def run(self, cmd: str) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            self.get_cmd(cmd),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        prefix = (self.envs or {}).get("WINEPREFIX")
        if prefix:
            self._running.setdefault(prefix, []).append(proc)
        return proc

    @classmethod
    def terminate_prefix(cls, prefix: str, sig: int = signal.SIGKILL) -> int:
        """Kill the process group of every sandbox launcher started for the
        given WINEPREFIX. Returns how many were signalled. Finished launchers
        are pruned."""
        killed = 0
        for proc in cls._running.get(prefix, []):
            if proc.poll() is not None:
                continue
            try:
                os.killpg(os.getpgid(proc.pid), sig)
                killed += 1
            except (ProcessLookupError, PermissionError, OSError):
                pass
        cls._running[prefix] = []
        return killed
