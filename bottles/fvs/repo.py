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
import json
import tempfile
from concurrent.futures import CancelledError
from contextlib import contextmanager
from datetime import datetime
from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock
from threading import Lock

from bottles.fvs.exceptions import (
    FVSNothingToCommit,
    FVSNothingToRestore,
    FVSStateNotFound,
)

FVS2_CMD = "fvs2"

# fvs2 stores each block as a separate file in a flat .fvs2/blocks/ directory.
# With the upstream 4KiB default a large prefix (e.g. a game bottle) ends up
# split into millions of tiny files, which fills the inode table and makes
# external sync tools crawl. A bigger block size keeps the file count sane.
# The value is persisted per repo at init time, so existing repos keep their
# own block size and are left untouched.
DEFAULT_BLOCK_SIZE = 1048576  # 1 MiB

class FVSRepo:
    _REPO_LOCKS = {}
    _REPO_LOCKS_LOCK = Lock()

    def __init__(self, repo_path: str, use_compression: bool = False, no_init: bool = False, block_size: int = DEFAULT_BLOCK_SIZE):
        self._repo_path = repo_path
        self._use_compression = use_compression
        self._block_size = block_size
        self._fvs2 = self._get_fvs2_bin()
        self._lock = self._get_repo_lock(repo_path)
        
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

    @contextmanager
    def _commit_lock(self, cancel_event=None):
        lock_path = os.path.join(self._repo_path, ".fvs2", ".bottles.lock")
        lock_file = open(lock_path, "a+")
        try:
            while True:
                try:
                    flock(lock_file, LOCK_EX | LOCK_NB)
                    break
                except BlockingIOError:
                    if cancel_event and cancel_event.is_set():
                        raise CancelledError
                    time.sleep(0.1)
            yield
        finally:
            flock(lock_file, LOCK_UN)
            lock_file.close()

    @classmethod
    def _get_repo_lock(cls, repo_path):
        repo_path = os.path.realpath(repo_path)
        with cls._REPO_LOCKS_LOCK:
            return cls._REPO_LOCKS.setdefault(repo_path, Lock())

    def _commit_metadata_paths(self):
        meta_path = os.path.join(self._repo_path, ".fvs2")
        head_path = os.path.join(meta_path, "HEAD.json")
        index_path = os.path.join(meta_path, "index.json")
        paths = [head_path]

        try:
            with open(head_path, "rb") as head_file:
                head = json.load(head_file)
        except FileNotFoundError:
            head = {"type": "branch", "name": "main"}

        if head.get("type") == "branch":
            branch = head.get("name") or "main"
            if (
                not isinstance(branch, str)
                or ".." in branch
                or os.path.basename(branch) != branch
            ):
                raise RuntimeError("Invalid FVS branch metadata")
            paths.append(os.path.join(meta_path, "refs", "heads", branch))

        paths.append(index_path)
        return paths

    def _snapshot_commit_metadata(self):
        snapshot = {}
        for path in self._commit_metadata_paths():
            try:
                with open(path, "rb") as metadata_file:
                    snapshot[path] = (
                        metadata_file.read(),
                        os.fstat(metadata_file.fileno()).st_mode & 0o777,
                    )
            except FileNotFoundError:
                snapshot[path] = None
        return snapshot

    def _snapshot_repository_files(self):
        meta_path = os.path.join(self._repo_path, ".fvs2")
        files = set()
        for directory, _subdirectories, filenames in os.walk(meta_path):
            for filename in filenames:
                path = os.path.join(directory, filename)
                files.add(os.path.relpath(path, meta_path))
        return files

    @staticmethod
    def _sync_directory(path):
        directory = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _restore_commit_metadata(self, snapshot):
        for path, original in snapshot.items():
            directory = os.path.dirname(path)
            if original is None:
                try:
                    os.remove(path)
                    self._sync_directory(directory)
                except FileNotFoundError:
                    pass
                continue

            data, mode = original
            file_descriptor, temp_path = tempfile.mkstemp(
                prefix=".bottles-cancel-",
                dir=directory,
            )
            try:
                with os.fdopen(file_descriptor, "wb") as metadata_file:
                    metadata_file.write(data)
                    metadata_file.flush()
                    os.fchmod(metadata_file.fileno(), mode)
                    os.fsync(metadata_file.fileno())
                os.replace(temp_path, path)
                self._sync_directory(directory)
            finally:
                try:
                    os.remove(temp_path)
                except FileNotFoundError:
                    pass

    def _discard_cancelled_commit(self, metadata_snapshot, repository_files):
        self._restore_commit_metadata(metadata_snapshot)
        meta_path = os.path.join(self._repo_path, ".fvs2")
        for directory, _subdirectories, filenames in os.walk(meta_path):
            for filename in filenames:
                path = os.path.join(directory, filename)
                relative_path = os.path.relpath(path, meta_path)
                if relative_path not in repository_files:
                    os.remove(path)

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
                res = self._run_cmd("init", "--block-size", str(self._block_size), check=False)
                if res.returncode != 0 and "already initialized" not in res.stderr:
                    raise RuntimeError(f"Failed to initialize FVS: {res.stderr}")

    def commit(
        self,
        message: str,
        ignore: list = None,
        task_id: str = None,
        cancel_event=None,
    ):
        """Create a commit. Does NOT auto-refresh; caller should refresh if needed."""
        from bottles.backend.state import TaskManager

        if cancel_event and cancel_event.is_set():
            raise CancelledError
        
        with self._lock, self._commit_lock(cancel_event):
            metadata_snapshot = (
                self._snapshot_commit_metadata()
                if cancel_event is not None
                else None
            )
            repository_files = (
                self._snapshot_repository_files()
                if cancel_event is not None
                else None
            )
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
            captured_stdout = ""
            pending_stdout = ""

            def output_text(output):
                if isinstance(output, bytes):
                    return output.decode(errors="replace")
                return output or ""

            def update_progress(output, flush=False):
                nonlocal captured_stdout, last_update, pending_stdout
                output = output_text(output)
                if output.startswith(captured_stdout):
                    pending_stdout += output[len(captured_stdout):]
                else:
                    pending_stdout += output
                captured_stdout = output

                lines = pending_stdout.splitlines(keepends=True)
                pending_stdout = ""
                for line in lines:
                    if not flush and not line.endswith(("\n", "\r")):
                        pending_stdout = line
                        continue
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

            while True:
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    update_progress(stdout, flush=True)
                    break
                except subprocess.TimeoutExpired as error:
                    update_progress(error.output)
                    if not cancel_event or not cancel_event.is_set():
                        continue

                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                        stdout, stderr = process.communicate()

                    if process.returncode == 0:
                        update_progress(stdout, flush=True)
                        break

                    self._discard_cancelled_commit(
                        metadata_snapshot,
                        repository_files,
                    )
                    raise CancelledError
            
            if process.returncode != 0:
                full_stdout = output_text(stdout).lower()
                full_stderr = output_text(stderr).lower()
                if "nothing to commit" in full_stdout or "nothing to commit" in full_stderr:
                    raise FVSNothingToCommit()
                raise RuntimeError(f"FVS commit failed: {stderr}")

    def restore_state(self, state_id: str, ignore: list = None, reset: bool = True, task_id: str = None):
        """Restore to a state. Does NOT auto-refresh; caller should refresh if needed."""
        from bottles.backend.state import TaskManager
        with self._lock, self._commit_lock():
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
        with self._lock, self._commit_lock():
            res = self._run_cmd("branch", "create", branch_name, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS create branch failed: {res.stderr}")

    def delete_branch(self, branch_name: str):
        """Delete a branch. Does NOT auto-refresh; caller should refresh if needed."""
        with self._lock, self._commit_lock():
            res = self._run_cmd("branch", "delete", branch_name, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS delete branch failed: {res.stderr}")

    def checkout(self, target: str):
        """Switch HEAD to a branch. Does NOT auto-refresh; caller should refresh if needed."""
        with self._lock, self._commit_lock():
            res = self._run_cmd("checkout", target, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"FVS checkout failed: {res.stderr}")
