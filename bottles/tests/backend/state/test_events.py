"""EventManager tests"""
import time
from enum import Enum
from threading import Thread
import pytest

from bottles.backend.state import EventManager

class Events(Enum):
    SimpleEvent = "simple.event"
    WaitAfterDone = "wait_after_done.event"
    SetResetEvent = "set_reset.event"
    WaitSingleton = "wait_singleton.event"
    DoneSingleton = "done_singleton.event"
    CorrectFlagDone = "correct_flag_done.event"

def approx_time(start, target):
    epsilon = 0.010 # 5 ms window
    variation = time.time() - start - target
    result = -epsilon / 2 <= variation <= epsilon / 2
    if not result:
        print(f"Start: {start}")
        print(f"End: {variation + start + target}")
        print(f"Variation: {variation}")
    return result

def test_simple_event():
    start_time = time.time()
    def t1_func():
        EventManager.wait(Events.SimpleEvent)

    t1 = Thread(target=t1_func)
    t1.start()

    time.sleep(0.2)
    EventManager.done(Events.SimpleEvent)

    t1.join()
    assert approx_time(start_time, 0.2)


def test_wait_after_done_event():
    start_time = time.time()
    EventManager.done(Events.WaitAfterDone)

    EventManager.wait(Events.WaitAfterDone)
    assert approx_time(start_time, 0)

@pytest.mark.filterwarnings("error")
def test_set_reset():
    start_time = time.time()
    def t1_func():
        start_time_t1 = time.time()
        EventManager.wait(Events.SetResetEvent)
        assert approx_time(start_time_t1, 0.1)

    def t2_func():
        start_time_t1 = time.time()
        EventManager.wait(Events.SetResetEvent)
        assert approx_time(start_time_t1, 0)

    t1 = Thread(target=t1_func)
    t1.start()

    time.sleep(0.1)
    EventManager.done(Events.SetResetEvent)

    # Assert wait for 0.1s
    t1.join()

    t2 = Thread(target=t2_func)
    t2.start()
    # Assert wait for 0s
    t2.join()

    time.sleep(0.1)

    EventManager.reset(Events.SetResetEvent)

    t1 = Thread(target=t1_func)
    t1.start()

    time.sleep(0.1)
    EventManager.done(Events.SetResetEvent)

    # Assert wait for 0.1s
    t1.join()
    assert approx_time(start_time, 0.3)

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
