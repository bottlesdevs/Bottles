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

def approx_time(start, target):
    epsilon = 0.005 # 5 ms window
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
