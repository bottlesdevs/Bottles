import dataclasses
from enum import Enum
from gettext import gettext as _
from threading import Lock as PyLock, Event as PyEvent
from typing import Dict, Callable, Optional, Union, Protocol
from uuid import UUID, uuid4


class Locks(Enum):
    ComponentsInstall = "components.install"


class Status(Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskStreamUpdateHandler(Protocol):
    def __call__(self, received_size: int = 0, total_size: int = 0, status: Status = None) -> None: ...


@dataclasses.dataclass
class Task:
    _task_id: Optional[UUID] = None  # should only be set by TaskManager
    title: str = "Task"
    _subtitle: str = ""
    hidden: bool = False  # hide from UI
    cancellable: bool = False

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @task_id.setter
    def task_id(self, value: UUID):
        if self._task_id is not None:
            raise NotImplementedError("Invalid usage, Task.task_id should only set once")
        self._task_id = value

    @property
    def subtitle(self) -> str:
        return self._subtitle

    @subtitle.setter
    def subtitle(self, value: str):
        self._subtitle = value
        # TODO: sync signal

    def stream_update(self, received_size: int = 0, total_size: int = 0, status: Status = None):
        """This is a default subtitle updating handler for streaming downloading progress"""
        match status:
            case Status.DONE, Status.FAILED:
                TaskManager.remove_task(self)
                return
            case _:
                pass

        if total_size == 0 and received_size == 0:
            self.subtitle = _("Calculating…")
            return

        percent = int(received_size / total_size * 100)
        self.subtitle = f"{percent}%"


class LockManager:
    _LOCKS: Dict[str, PyLock] = {}  # {"lock_name": Lock}

    @classmethod
    def lock(cls, name: Locks):
        """decorator, used for mutex locking the decorated function"""
        lock = cls.get_lock(name)

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


class TaskManager:
    """Long-running tasks are registered here, for tracking and display them on UI"""
    _TASKS: Dict[UUID, Task] = {}  # {UUID4: Task}

    @classmethod
    def get_task(cls, task_id: UUID) -> Optional[Task]:
        return cls._TASKS.get(task_id)

    @classmethod
    def add_task(cls, task: Task) -> UUID:
        """register a running task to TaskManager"""
        uniq = uuid4()
        task.task_id = uniq
        cls._TASKS[uniq] = task
        # TODO: sync signal
        return uniq

    @classmethod
    def remove_task(cls, task: Union[UUID, Task]):
        if isinstance(task, Task):
            task = task.task_id
        cls._TASKS.pop(task)
        # TODO: sync signal


class State(LockManager, EventManager, TaskManager):
    """Unified State Management"""
    pass
