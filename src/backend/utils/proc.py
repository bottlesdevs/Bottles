# proc.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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

import os
import subprocess


class Proc:
    def __init__(self, pid):
        self.pid = pid

    def __get_data(self, data):
        try:
            with open(os.path.join('/proc', str(self.pid), data), 'rb') as f:
                return f.read().decode('utf-8')
        except (FileNotFoundError, PermissionError):
            return ""

    def get_cmdline(self):
        return self.__get_data('cmdline')

    def get_env(self):
        return self.__get_data('environ')

    def get_cwd(self):
        return self.__get_data('cwd')

    def get_name(self):
        return self.__get_data('stat')

    def kill(self):
        subprocess.Popen(['kill', str(self.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ProcUtils:

    @staticmethod
    def get_procs():
        procs = []
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                procs.append(Proc(pid))
        return procs

    @staticmethod
    def get_by_cmdline(cmdline):
        _procs = ProcUtils.get_procs()
        return [proc for proc in _procs if cmdline in proc.get_cmdline()]

    @staticmethod
    def get_by_env(env):
        _procs = ProcUtils.get_procs()
        return [proc for proc in _procs if env in proc.get_env()]

    @staticmethod
    def get_by_cwd(cwd):
        _procs = ProcUtils.get_procs()
        return [proc for proc in _procs if cwd in proc.get_cwd()]

    @staticmethod
    def get_by_name(name):
        _procs = ProcUtils.get_procs()
        return [proc for proc in _procs if name in proc.get_name()]

    @staticmethod
    def get_by_pid(pid):
        return Proc(pid)
