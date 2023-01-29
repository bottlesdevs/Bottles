import dataclasses
from enum import Enum
from threading import Lock as PyLock, Event as PyEvent
from typing import Dict, Callable, Union
from uuid import UUID, uuid4


class Locks(Enum):
    ComponentsInstall = "components.install"


class Status(Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclasses.dataclass
class Task:
    title: str = ""
    description: str = ""
    hidden: bool = False  # hide from UI
    cancellable: bool = False


class LockService:
    _LOCKS: Dict[str, PyLock] = {}  # {"lock_name": Lock}

    @classmethod
    def lock(cls, name: Locks):
        """decorator, used for mutex locking the decorated function"""
        lock = cls._LOCKS.setdefault(name.value, PyLock())

        def func_wrapper(func: Callable):
            def wrapper(*args, **kwargs):
                lock.acquire()
                rv = func(*args, **kwargs)
                lock.release()
                return rv

            return wrapper

        return func_wrapper

    @classmethod
    def get_lock(cls, name: Locks) -> PyLock:
        return cls._LOCKS.setdefault(name.value, PyLock())


class EventManager:
    _EVENTS: Dict[str, PyEvent] = {}  # {"event_name": Event}


class StatusManager:
    _STATUS: Dict[str, Status] = {}  # {"status_name": status}


class TaskManager:
    _TASKS: Dict[str, Task]  # {"task_id(uuid4 str)": Task}

    @classmethod
    def add_task(cls, task: Task) -> UUID:
        """add a """
        uniq = uuid4()
        cls._TASKS[str(uniq)] = task
        return uniq

    @classmethod
    def remove_task(cls, uuid: Union[str, UUID]):
        cls._TASKS.pop(str(uuid))


class State(LockService, EventManager, StatusManager, TaskManager):
    """Unified State Management"""
    pass
