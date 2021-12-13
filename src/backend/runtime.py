import os
from pathlib import Path


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
                for dir in dirs:
                    structure_found.append(dir)

            if not check_structure(structure_found, structure ):
                continue
            
            res = []
            for s in structure:
                res.append(f"{runtime_path}/{s}")

            return res
        
        return False
    
    def __get_bottles_runtime():
        paths = [
            f"/app/etc/runtime",
            f"{Path.home()}/.local/share/bottles/runtime",
        ]
        structure = ["lib32", "lib64"]

        return RuntimeManager.__get_runtime(paths, structure)
    
    def __get_steam_runtime():
        # NOTE: Not implemented, here just for testing purposes
        paths = [
            f"{Path.home()}/.local/share/Steam/ubuntu12_32/steam-runtime/lib",
            f"{Path.home()}/.var/app/com.valvesoftware.Steam/data/Steam/ubuntu12_32/steam-runtime/lib"
        ]
        structure = ["i386-linux-gnu", "x86_64-linux-gnu"]

        return RuntimeManager.__get_runtime(paths, structure)
