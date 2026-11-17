"""EventManager tests"""

from enum import Enum
from threading import Event, Thread

from bottles.backend.state import EventManager


class Events(Enum):
    SimpleEvent = "simple.event"
    WaitAfterDone = "wait_after_done.event"
    SetResetEvent = "set_reset.event"
    WaitSingleton = "wait_singleton.event"
    DoneSingleton = "done_singleton.event"
    CorrectFlagDone = "correct_flag_done.event"


def test_simple_event():
    completed = Event()

    def wait_thread():
        EventManager.wait(Events.SimpleEvent)
        completed.set()

    thread = Thread(target=wait_thread, daemon=True)
    thread.start()
    try:
        assert not completed.wait(0.05)
        EventManager.done(Events.SimpleEvent)
        assert completed.wait(2)
    finally:
        EventManager.done(Events.SimpleEvent)
        thread.join(2)


def test_wait_after_done_event():
    EventManager.done(Events.WaitAfterDone)
    thread = Thread(target=EventManager.wait, args=(Events.WaitAfterDone,), daemon=True)
    thread.start()
    thread.join(2)
    assert not thread.is_alive()


def test_set_reset():
    completed = Event()

    def wait_thread():
        EventManager.wait(Events.SetResetEvent)
        completed.set()

    for _ in range(2):
        completed.clear()
        EventManager.reset(Events.SetResetEvent)
        thread = Thread(target=wait_thread, daemon=True)
        thread.start()
        try:
            assert not completed.wait(0.05)
            EventManager.done(Events.SetResetEvent)
            assert completed.wait(2)
        finally:
            EventManager.done(Events.SetResetEvent)
            thread.join(2)

        completed.clear()
        thread = Thread(target=wait_thread, daemon=True)
        thread.start()
        thread.join(2)
        assert completed.is_set()
        assert not thread.is_alive()


def test_event_singleton_wait():
    EventManager._EVENTS = {}

    def wait_thread():
        EventManager.wait(Events.WaitSingleton)

    def wait_thread_by_value():
        EventManager.wait(Events("wait_singleton.event"))

    t1 = Thread(target=wait_thread)
    t1.start()

    t2 = Thread(target=wait_thread)
    t2.start()

    t3 = Thread(target=wait_thread_by_value)
    t3.start()

    assert len(EventManager._EVENTS) == 1

    EventManager.done(Events.WaitSingleton)
    t1.join()
    t2.join()
    t3.join()


def test_event_singleton_done_reset():
    EventManager._EVENTS = {}

    EventManager.done(Events.DoneSingleton)
    EventManager.done(Events.DoneSingleton)
    assert len(EventManager._EVENTS) == 1

    EventManager.reset(Events.DoneSingleton)
    assert len(EventManager._EVENTS) == 1

    EventManager.reset(Events.DoneSingleton)
    assert len(EventManager._EVENTS) == 1


def test_correct_internal_flag():
    EventManager.done(Events.CorrectFlagDone)

    assert EventManager._EVENTS[Events.CorrectFlagDone].is_set()

    EventManager.reset(Events.CorrectFlagDone)

    assert not EventManager._EVENTS[Events.CorrectFlagDone].is_set()
