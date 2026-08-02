# ruff: noqa: E402

from types import SimpleNamespace

import pytest
from gi.repository import Gio

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Task, TaskManager
from bottles.frontend.operation import TaskEntry, TaskSyncer


@pytest.fixture(autouse=True)
def isolated_tasks():
    tasks = TaskManager._TASKS
    signals = SignalManager._SIGNALS
    TaskManager._TASKS = {}
    SignalManager._SIGNALS = {}
    yield
    TaskManager._TASKS = tasks
    SignalManager._SIGNALS = signals


def test_task_entry_cancel_requests_backend_cancellation():
    task = Task(cancellable=True)
    task_id = TaskManager.add(task)
    button = SimpleNamespace(
        set_sensitive=lambda value: setattr(button, "sensitive", value)
    )
    row = SimpleNamespace(task_id=task_id, btn_cancel=button)

    TaskEntry._TaskEntry__cancel_task(row, button)

    assert task.cancel_event.is_set()
    assert button.sensitive is False


def test_task_syncer_ignores_update_after_task_removal():
    task = Task(cancellable=True)
    task_id = TaskManager.add(task)
    TaskManager.remove(task_id)
    syncer = SimpleNamespace(
        _TASK_WIDGETS={task_id: SimpleNamespace(update=lambda **_kwargs: None)}
    )

    TaskSyncer.task_updated_handler.__wrapped__(syncer, Result(True, task_id))


def test_task_syncer_ignores_add_after_task_removal():
    task = Task(cancellable=True)
    task_id = TaskManager.add(task)
    TaskManager.remove(task_id)
    syncer = SimpleNamespace()

    TaskSyncer.task_added_handler.__wrapped__(syncer, Result(True, task_id))
