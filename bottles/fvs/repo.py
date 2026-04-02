# repo.py
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
import time
import subprocess
from datetime import datetime
from threading import Lock

from bottles.fvs.exceptions import (
    FVSNothingToCommit,
    FVSNothingToRestore,
    FVSStateNotFound,
)

FVS2_CMD = "fvs2"

class FVSRepo:
    def __init__(self, repo_path: str, use_compression: bool = False, no_init: bool = False):
        self._repo_path = repo_path
        self._use_compression = use_compression
        self._fvs2 = self._get_fvs2_bin()
        self._lock = Lock()
        
        self.__states = {}
        self.__active_state_id = None
        self.__active_branch = None
        self.__branches = []
        self.__has_no_states = True
        self.__dirty = False
        self.__changed_files = 0
        
        if not no_init:
            self._init_repo()
            
        self._refresh()

    def _get_fvs2_bin(self):
        return "fvs2"

    def _run_cmd(self, *args, check=True):
        cmd = [self._fvs2] + list(args)
        return subprocess.run(cmd, cwd=self._repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)

    def _init_repo(self):
        if not os.path.exists(os.path.join(self._repo_path, ".fvs2")):
            # Prevent auto-init if legacy systems are found
            if os.path.exists(os.path.join(self._repo_path, ".fvs")) or \
               os.path.exists(os.path.join(self._repo_path, "states", "states.yml")):
                logging.info("Legacy versioning detected, skipping FVS2 auto-init")
                return

            with self._lock:
                res = self._run_cmd("init", check=False)
                if res.returncode != 0 and "already initialized" not in res.stderr:
                    raise RuntimeError(f"Failed to initialize FVS: {res.stderr}")

    def commit(self, message: str, ignore: list = None, task_id: str = None):
        """Create a commit. Does NOT auto-refresh; caller should refresh if needed."""
        from bottles.backend.state import TaskManager
        
        with self._lock:
            args = [self._fvs2, "commit", "-m", message, "-v"]
            
            process = subprocess.Popen(
                args,
                cwd=self._repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            last_update = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    if line.startswith("hashing: "):
                        current_time = time.time()
                        if current_time - last_update > 0.1:
                            file_path = line.replace("hashing: ", "")
                            if task_id:
                                task = TaskManager.get(task_id)
                                if task:
                                    task.subtitle = file_path
                            last_update = current_time
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                full_stdout = stdout.lower()
                full_stderr = stderr.lower()
                if "nothing to commit" in full_stdout or "nothing to commit" in full_stderr:
                    raise FVSNothingToCommit()
                raise RuntimeError(f"FVS commit failed: {stderr}")

    def restore_state(self, state_id: str, ignore: list = None, reset: bool = True, task_id: str = None):
        """Restore to a state. Does NOT auto-refresh; caller should refresh if needed."""
        from bottles.backend.state import TaskManager
        with self._lock:
            state_id = str(state_id)
            matched = False
            for k in self.__states.keys():
                if state_id.startswith(k) or k.startswith(state_id):
                    state_id = k
                    matched = True
                    break
            if not matched:
                raise FVSStateNotFound(state_id)
                
            args = [self._fvs2, "restore", "-s", state_id, "-v"]
            if reset:
                args.append("--reset")
                
            process = subprocess.Popen(
                args,
                cwd=self._repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            last_update = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    if line.startswith("restoring: "):
                        current_time = time.time()
                        if current_time - last_update > 0.1:
                            file_path = line.replace("restoring: ", "")
                            if task_id:
                                task = TaskManager.get(task_id)
                                if task:
                                    task.subtitle = file_path
                            last_update = current_time
                                
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                if "nothing to restore" in stderr.lower():
                    raise FVSNothingToRestore()
                raise RuntimeError(f"FVS restore failed: {stderr}")

    def _refresh(self):
        """Fetch status, states and branches in one pass."""
        with self._lock:
            self.__states = {}
            self.__active_state_id = None
            self.__active_branch = None
            self.__branches = []
            self.__has_no_states = True
            
            if not os.path.exists(os.path.join(self._repo_path, ".fvs2")):
                return

            status_res = self._run_cmd("status", check=False)
            if status_res.returncode == 0:
                for sline in status_res.stdout.split("\n"):
                    if sline.startswith("head_commit="):
                        self.__active_state_id = sline.replace("head_commit=", "").strip()
                    elif sline.startswith("branch="):
                        self.__active_branch = sline.replace("branch=", "").strip()

            states_res = self._run_cmd("states", check=False)
            if states_res.returncode == 0:
                for line in states_res.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("  ", 2)
                    if len(parts) >= 3:
                        state_id = parts[0].strip()
                        time_str = parts[1].strip()
                        message = parts[2].strip()
                        try:
                            dt = datetime.strptime(time_str.split(".")[0].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                            timestamp = int(datetime.timestamp(dt))
                        except:
                            timestamp = int(datetime.timestamp(datetime.now()))
                        self.__states[state_id] = {
                            "timestamp": timestamp,
                            "message": message,
                        }
                if self.__states:
                    self.__has_no_states = False

            branches_res = self._run_cmd("branch", "list", check=False)
            if branches_res.returncode == 0:
                self.__branches = [b.strip().lstrip("* ") for b in branches_res.stdout.split("\n") if b.strip()]

    def check_dirty(self):
        """Specifically runs the slow dirty check and updates the dirty/changed_files properties."""
        with self._lock:
            if not os.path.exists(os.path.join(self._repo_path, ".fvs2")):
                return
            res = self._run_cmd("status", "--check-dirty", check=False)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    sline = line.strip().lower()
                    if sline.startswith("dirty="):
                        self.__dirty = sline.replace("dirty=", "").strip() == "true"
                    elif sline.startswith("changed_files="):
                        try:
                            self.__changed_files = int(sline.replace("changed_files=", "").strip())
                        except ValueError:
                            pass

    @property
    def has_no_states(self) -> bool:
        return self.__has_no_states

    @property
    def states(self) -> dict:
        return self.__states

    @property
    def active_state_id(self) -> str:
        return self.__active_state_id

    @property
    def active_branch(self) -> str:
        return self.__active_branch

    @property
    def dirty(self) -> bool:
        return self.__dirty

    @property
    def changed_files(self) -> int:
        return self.__changed_files

    @property
    def branches(self) -> list:
        return self.__branches
        
    def create_branch(self, branch_name: str):
        """Create a branch. Does NOT auto-refresh; caller should refresh if needed."""
        with self._lock:
            res = self._run_cmd("branch", "create", branch_name, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS create branch failed: {res.stderr}")

    def delete_branch(self, branch_name: str):
        """Delete a branch. Does NOT auto-refresh; caller should refresh if needed."""
        with self._lock:
            res = self._run_cmd("branch", "delete", branch_name, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS delete branch failed: {res.stderr}")

    def checkout(self, target: str):
        """Switch HEAD to a branch. Does NOT auto-refresh; caller should refresh if needed."""
        with self._lock:
            res = self._run_cmd("checkout", target, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS checkout failed: {res.stderr}")
