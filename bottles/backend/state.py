import dataclasses
from enum import Enum
from gettext import gettext as _
from threading import Lock as PyLock, Event as PyEvent
from typing import Protocol
from collections.abc import Callable
from uuid import UUID, uuid4

import logging
from bottles.backend.models.result import Result


class Locks(Enum):
    ComponentsInstall = "components.install"


class Events(Enum):
    ComponentsFetching = "components.fetching"
    DependenciesFetching = "dependencies.fetching"
    InstallersFetching = "installers.fetching"
    ComponentsOrganizing = "components.organizing"
    DependenciesOrganizing = "dependencies.organizing"
    InstallersOrganizing = "installers.organizing"


class Signals(Enum):
    """Signals backend support"""

    ManagerLocalBottlesLoaded = "Manager.local_bottles_loaded"  # no extra data

    ForceStopNetworking = (
        "LoadingView.stop_networking"  # status(bool): Force Stop network operations
    )
    NetworkStatusChanged = (
        "ConnectionUtils.status_changed"  # status(bool): network ready or not
    )

    GNotification = (
        "G.send_notification"  # data(Notification): data for Gio notification
    )
    GShowUri = "G.show_uri"  # data(str): the URI

    # data(UUID): the UUID of task
    TaskAdded = "task.added"
    TaskRemoved = "task.removed"
    TaskUpdated = "task.updated"


class Status(Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskStreamUpdateHandler(Protocol):
    def __call__(
        self,
        received_size: int = 0,
        total_size: int = 0,
        status: Status | None = None,
    ) -> None: ...


class SignalHandler(Protocol):
    def __call__(self, data: Result | None = None) -> None: ...


@dataclasses.dataclass
class Notification:
    title: str = "Bottles"
    text: str = "no message provided"
    image: str = ""


@dataclasses.dataclass(init=False)
class Task:
    _task_id: UUID | None = None  # should only be set by TaskManager
    title: str = "Task"
    _subtitle: str = ""
    hidden: bool = False  # hide from UI
    cancellable: bool = False

    def __init__(
        self,
        title: str = "Task",
        subtitle: str = "",
        hidden: bool = False,
        cancellable: bool = False,
    ):
        self.title = title
        self.subtitle = subtitle
        self.hidden = hidden
        self.cancellable = cancellable

    @property
    def task_id(self) -> UUID | None:
        return self._task_id

    @task_id.setter
    def task_id(self, value: UUID):
        if self._task_id is not None:
            raise NotImplementedError(
                "Invalid usage, Task.task_id should only set once"
            )
        self._task_id = value

    @property
    def subtitle(self) -> str:
        return self._subtitle

    @subtitle.setter
    def subtitle(self, value: str):
        self._subtitle = value
        SignalManager.send(Signals.TaskUpdated, Result(True, self.task_id))

    def stream_update(
        self,
        received_size: int = 0,
        total_size: int = 0,
        status: Status | None = None,
    ):
        """This is a default subtitle updating handler for streaming downloading progress"""
        match status:
            case Status.DONE | Status.FAILED:
                TaskManager.remove(self)
                return
            case _:
                pass

        if total_size == 0 and received_size == 0:
            self.subtitle = _("Calculating…")
            return

        percent = int(received_size / total_size * 100)
        self.subtitle = f"{percent}%"


class LockManager:
    _LOCKS: dict[Locks, PyLock] = {}

    @classmethod
    def lock(cls, name: Locks):
        """decorator, used for mutex locking the decorated function"""
        lock = cls.get(name)

        def func_wrapper(func: Callable):
            def wrapper(*args, **kwargs):
                lock.acquire()
                rv = func(*args, **kwargs)
                lock.release()
                return rv

            return wrapper

        return func_wrapper

    @classmethod
    def get(cls, name: Locks) -> PyLock:
        return cls._LOCKS.setdefault(name, PyLock())


class EventManager:
    """
    This class manages events, which are one-time events (can be reset) during the lifecycle of the app.
    You can wait for the event to occur, or set it when the associated operations are finished.
    Wait for an event that has already been set, will immediately return.
    """

    _EVENTS: dict[Events, PyEvent] = {}

    @classmethod
    def wait(cls, event: Events):
        _event = cls._EVENTS.setdefault(event, PyEvent())
        # By default, when an Event is created, it will be unset, so it will block
        logging.debug(f"Waiting on operation {event}")
        _event.wait()
        logging.debug(f"Done wait operation {event}")

    @classmethod
    def done(cls, event: Events):
        _event = cls._EVENTS.setdefault(event, PyEvent())
        _event.set()
        logging.debug(f"Done operation {event}")

    @classmethod
    def reset(cls, event: Events):
        _event = cls._EVENTS.setdefault(event, PyEvent())
        _event.clear()
        logging.debug(f"Reset operation {event}")


class TaskManager:
    """Long-running tasks are registered here, for tracking and display them on UI"""

    _TASKS: dict[UUID, Task] = {}  # {UUID4: Task}

    @classmethod
    def get(cls, task_id: UUID) -> Task | None:
        return cls._TASKS.get(task_id)

    @classmethod
    def add(cls, task: Task) -> UUID:
        """register a running task to TaskManager"""
        uniq = uuid4()
        task.task_id = uniq
        cls._TASKS[uniq] = task
        SignalManager.send(Signals.TaskAdded, Result(True, task.task_id))
        return uniq

    @classmethod
    def remove(cls, task: UUID | Task):
        if isinstance(task, Task):
            task = task.task_id
        cls._TASKS.pop(task)
        SignalManager.send(Signals.TaskRemoved, Result(True, task))


class SignalManager:
    """sync backend state to frontend via registered signal handlers"""

    _SIGNALS: dict[Signals, list[SignalHandler]] = {}

    @classmethod
    def connect(cls, signal: Signals, handler: SignalHandler) -> None:
        cls._SIGNALS.setdefault(signal, [])
        cls._SIGNALS[signal].append(handler)

    @classmethod
    def send(cls, signal: Signals, data: Result | None = None) -> None:
        """
        Send signal
        should only be called by backend logic
        """
        if signal not in cls._SIGNALS:
            logging.debug(f"No handler registered for {signal}")
            return
        for fn in cls._SIGNALS[signal]:
            fn(data)
