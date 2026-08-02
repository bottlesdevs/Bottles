import subprocess
import sys
import time
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event
from threading import Thread

import pytest

from bottles.backend.state import SignalManager, Task, TaskManager
from bottles.fvs.repo import FVSRepo


@pytest.fixture(autouse=True)
def isolated_tasks():
    tasks = TaskManager._TASKS
    signals = SignalManager._SIGNALS
    TaskManager._TASKS = {}
    SignalManager._SIGNALS = {}
    yield
    TaskManager._TASKS = tasks
    SignalManager._SIGNALS = signals


def make_repo(tmp_path):
    meta_path = tmp_path / ".fvs2"
    ref_path = meta_path / "refs" / "heads" / "main"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    (meta_path / "HEAD.json").write_text('{"type": "branch", "name": "main"}\n')
    (meta_path / "index.json").write_text('{"commits": null}\n')
    ref_path.write_text("old-head\n")
    repo = object.__new__(FVSRepo)
    repo._repo_path = str(tmp_path)
    repo._fvs2 = "fvs2"
    repo._lock = FVSRepo._get_repo_lock(str(tmp_path))
    return repo


def read_metadata(path):
    meta_path = Path(path) / ".fvs2"
    return (
        (meta_path / "HEAD.json").read_bytes(),
        (meta_path / "index.json").read_bytes(),
        (meta_path / "refs" / "heads" / "main").read_bytes(),
    )


class FakeProcess:
    def __init__(self, cancel_event, repo_path, stage, stubborn=False):
        self.cancel_event = cancel_event
        self.repo_path = Path(repo_path)
        self.stage = stage
        self.stubborn = stubborn
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.calls = 0

    def mutate_metadata(self):
        meta_path = self.repo_path / ".fvs2"
        (meta_path / "commits").mkdir(exist_ok=True)
        (meta_path / "commits" / "new-state.json").write_text("new commit")
        (meta_path / "blocks").mkdir(exist_ok=True)
        (meta_path / "blocks" / "new-block").write_text("new block")
        if self.stage in ("index", "head"):
            (meta_path / "index.json").write_text('{"commits": ["new"]}\n')
        if self.stage == "head":
            (meta_path / "refs" / "heads" / "main").write_text("new-head\n")

    def communicate(self, timeout=None):
        self.calls += 1
        if self.killed:
            self.returncode = -9
            return ("", "")
        if self.terminated:
            if self.stubborn:
                raise subprocess.TimeoutExpired("fvs2", timeout)
            self.returncode = -15
            return ("", "")
        self.mutate_metadata()
        self.cancel_event.set()
        raise subprocess.TimeoutExpired(
            "fvs2",
            timeout,
            output=b"hashing: drive_c/program.exe\n",
        )

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


@pytest.mark.parametrize("stubborn", (False, True))
@pytest.mark.parametrize("stage", ("commit", "index", "head"))
def test_commit_terminates_process_on_cancellation(
    tmp_path, monkeypatch, stubborn, stage
):
    cancel_event = Event()
    repo = make_repo(tmp_path)
    before = read_metadata(tmp_path)
    process = FakeProcess(
        cancel_event,
        tmp_path,
        stage,
        stubborn=stubborn,
    )
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(CancelledError):
        repo.commit("snapshot", cancel_event=cancel_event)

    assert process.terminated
    assert process.killed is stubborn
    assert read_metadata(tmp_path) == before
    assert list((tmp_path / ".fvs2" / "commits").iterdir()) == []
    assert list((tmp_path / ".fvs2" / "blocks").iterdir()) == []


def test_commit_keeps_success_that_finishes_during_cancellation(tmp_path, monkeypatch):
    cancel_event = Event()
    repo = make_repo(tmp_path)

    class CompletedProcess(FakeProcess):
        def communicate(self, timeout=None):
            self.calls += 1
            if self.terminated:
                self.returncode = 0
                return ("hashing: drive_c/program.exe\n", "")
            self.mutate_metadata()
            self.cancel_event.set()
            raise subprocess.TimeoutExpired("fvs2", timeout)

    process = CompletedProcess(cancel_event, tmp_path, "head")
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)

    repo.commit("snapshot", cancel_event=cancel_event)

    assert process.returncode == 0
    assert read_metadata(tmp_path)[1:] == (
        b'{"commits": ["new"]}\n',
        b"new-head\n",
    )


def test_commit_holds_process_lock_during_cancelled_restore(tmp_path, monkeypatch):
    cancel_event = Event()
    repo = make_repo(tmp_path)
    restore_started = Event()
    allow_restore = Event()
    process = FakeProcess(cancel_event, tmp_path, "head")
    original_restore = repo._restore_commit_metadata
    original_popen = subprocess.Popen
    errors = []

    def restore(snapshot):
        restore_started.set()
        assert allow_restore.wait(1)
        original_restore(snapshot)

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(repo, "_restore_commit_metadata", restore)

    commit_thread = Thread(
        target=lambda: run_cancelled_commit(repo, cancel_event, errors),
    )
    commit_thread.start()
    assert restore_started.wait(1)

    acquired = tmp_path / "acquired"
    lock_process = original_popen(
        [
            sys.executable,
            "-c",
            """
import sys
from pathlib import Path
from bottles.fvs.repo import FVSRepo

repo = object.__new__(FVSRepo)
repo._repo_path = sys.argv[1]
print("ready", flush=True)
with repo._commit_lock():
    Path(sys.argv[2]).touch()
""",
            str(tmp_path),
            str(acquired),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert lock_process.stdout.readline() == "ready\n"
    time.sleep(0.2)
    assert not acquired.exists()

    allow_restore.set()
    commit_thread.join(1)
    assert not commit_thread.is_alive()
    assert errors == []
    assert lock_process.wait(1) == 0
    assert acquired.exists()


def run_cancelled_commit(repo, cancel_event, errors):
    try:
        repo.commit("snapshot", cancel_event=cancel_event)
    except CancelledError:
        return
    errors.append("commit did not cancel")


def test_commit_updates_task_while_process_is_running(tmp_path, monkeypatch):
    task = Task(cancellable=True)
    task_id = TaskManager.add(task)

    class CompletedProcess:
        returncode = 0

        def __init__(self):
            self.calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(
                    "fvs2",
                    timeout,
                    output=b"hashing: drive_c/program.exe\n",
                )
            return ("hashing: drive_c/program.exe\n", "")

    monkeypatch.setattr(
        subprocess, "Popen", lambda *_args, **_kwargs: CompletedProcess()
    )

    make_repo(tmp_path).commit(
        "snapshot", task_id=task_id, cancel_event=task.cancel_event
    )

    assert task.subtitle == "drive_c/program.exe"


def test_repo_lock_is_shared_by_repository_path(tmp_path):
    first = make_repo(tmp_path)
    second = make_repo(tmp_path)
    other_path = tmp_path / "other"
    other_path.mkdir()
    other = make_repo(other_path)

    assert first._lock is second._lock
    assert first._lock is not other._lock
