# runtime.py
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
from pathlib import Path

from bottles.backend.globals import Paths  # pyright: reportMissingImports=false


class RuntimeManager:
        
    def get_runtimes():
        runtimes = [
            RuntimeManager.__get_bottles_runtime()
        ]
        
        for runtime in runtimes:
            if runtime:
                return runtime
        
        return False
    
    def get_runtime_env():
        runtime = RuntimeManager.get_runtimes()

        env = ""
        if runtime:
            env = ':'.join(runtime)

        ld = os.environ.get('LD_LIBRARY_PATH')
        if ld:
            env += f":{ld}"

        return env

    def __get_runtime(paths: list, structure: list):
        def check_structure(found, expected):
            for e in expected:
                if e not in found:
                    return False
            return True

        for runtime_path in paths:
            if not os.path.exists(runtime_path):
                continue
            
            structure_found = []
            for root, dirs, files in os.walk(runtime_path):
                for d in dirs:
                    structure_found.append(d)

            if not check_structure(structure_found, structure ):
                continue
            
            res = [f"{runtime_path}/{s}" for s in structure]

            return res
        
        return False
    
    def __get_bottles_runtime():
        paths = [
            f"/app/etc/runtime",
            Paths.runtimes
        ]
        structure = ["lib", "lib32"]

        return RuntimeManager.__get_runtime(paths, structure)
    
    def __get_steam_runtime():
        # NOTE: Not implemented, here just for testing purposes
        paths = [
            f"{Path.home()}/.local/share/Steam/ubuntu12_32/steam-runtime/lib",
            f"{Path.home()}/.var/app/com.valvesoftware.Steam/data/Steam/ubuntu12_32/steam-runtime/lib"
        ]
        structure = ["i386-linux-gnu", "x86_64-linux-gnu"]

        return RuntimeManager.__get_runtime(paths, structure)
