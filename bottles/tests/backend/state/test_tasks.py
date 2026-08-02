from threading import Event
from uuid import uuid4

import pytest

from bottles.backend.state import SignalManager, Task, TaskManager


@pytest.fixture(autouse=True)
def isolated_tasks():
    tasks = TaskManager._TASKS
    signals = SignalManager._SIGNALS
    TaskManager._TASKS = {}
    SignalManager._SIGNALS = {}
    yield
    TaskManager._TASKS = tasks
    SignalManager._SIGNALS = signals


def test_task_manager_cancels_only_requested_task():
    first = Task(cancellable=True)
    second = Task(cancellable=True)
    first_id = TaskManager.add(first)
    TaskManager.add(second)

    assert TaskManager.cancel(first_id)
    assert first.cancel_event.is_set()
    assert first.subtitle == "Cancelling..."
    assert not second.cancel_event.is_set()


def test_task_manager_cancel_is_idempotent():
    task = Task(cancellable=True)
    task_id = TaskManager.add(task)

    assert TaskManager.cancel(task_id)
    assert TaskManager.cancel(task_id)


def test_task_manager_rejects_unknown_or_non_cancellable_task():
    task = Task()
    task_id = TaskManager.add(task)

    assert not TaskManager.cancel(task_id)
    assert not TaskManager.cancel(uuid4())
    assert not task.cancel_event.is_set()


def test_task_manager_remove_is_idempotent():
    task = Task()
    task_id = TaskManager.add(task)

    TaskManager.remove(task_id)
    TaskManager.remove(task_id)

    assert TaskManager._TASKS == {}


def test_task_uses_supplied_cancel_event():
    cancel_event = Event()
    task = Task(cancel_event=cancel_event)

    assert task.cancellable
    assert task.cancel_event is cancel_event
