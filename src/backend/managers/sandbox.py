# steam.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import subprocess


class SandboxManager:

    def __init__(
            self,
            envs: dict = None,
            chdir: str = None,
            clear_env: bool = False,
            share_paths_ro: list = None,
            share_paths_rw: list = None,
            share_net: bool = False,
            share_user: bool = False,
            share_host_ro: bool = True
    ):
        self.envs = envs
        self.chdir = chdir
        self.clear_env = clear_env
        self.share_paths_ro = share_paths_ro
        self.share_paths_rw = share_paths_rw
        self.share_net = share_net
        self.share_user = share_user
        self.share_host_ro = share_host_ro

    def __get_bwrap(self, cmd: str):
        _cmd = ["bwrap"]

        if self.envs:
            _cmd += [f"--setenv {k} {v}" for k, v in self.envs.items()]

        if self.share_host_ro:
            _cmd.append("--ro-bind / /")

        if self.chdir:
            _cmd.append(f"--chdir {self.chdir}")
            _cmd.append(f"--bind {self.chdir} {self.chdir}")

        if self.clear_env:
            _cmd.append("--clearenv")

        if self.share_paths_ro:
            _cmd += [f"--ro-bind {p} {p}" for p in self.share_paths_ro]

        if self.share_paths_rw:
            _cmd += [f"--bind {p} {p}" for p in self.share_paths_ro]

        _cmd.append("--share-net" if self.share_net else "--unshare-net")
        _cmd.append("--share-user" if self.share_user else "--unshare-user")
        _cmd.append(cmd)

        return _cmd

    def __get_flatpak_spawn(self, cmd: str):
        _cmd = ["flatpak-spawn"]

        if self.envs:
            _cmd += [f"--env={k}={v}" for k, v in self.envs.items()]

        if self.share_host_ro:
            _cmd.append("--sandbox")
            _cmd.append("--sandbox-expose-path-ro=/")

        if self.chdir:
            _cmd.append(f"--directory={self.chdir}")
            _cmd.append(f"--sandbox-expose-path={self.chdir}")

        if self.clear_env:
            _cmd.append("--clear-env")

        if self.share_paths_ro:
            _cmd += [f"--sandbox-expose-path-ro={p}" for p in self.share_paths_ro]

        if self.share_paths_rw:
            _cmd += [f"--sandbox-expose-path={p}" for p in self.share_paths_rw]

        if not self.share_net:
            _cmd.append("--no-network")

        _cmd.append(cmd)

        return _cmd

    def get_cmd(self, cmd: str):
        if "FLATPAK_ID" in os.environ:
            return self.__get_flatpak_spawn(cmd)
        return self.__get_bwrap(cmd)

    def run(self, cmd: str):
        return subprocess.Popen(self.get_cmd(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
