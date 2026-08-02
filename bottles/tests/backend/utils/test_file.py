import threading
from concurrent.futures import CancelledError

import pytest

from bottles.backend.utils.file import FileUtils


def test_wait_for_files_waits_until_file_exists(tmp_path):
    target = tmp_path / "system.reg"
    timer = threading.Timer(0.05, target.touch)
    timer.start()

    try:
        assert FileUtils.wait_for_files([str(target)], timeout=1)
    finally:
        timer.cancel()


def test_wait_for_files_times_out_for_missing_file(tmp_path):
    target = tmp_path / "missing.reg"

    assert not FileUtils.wait_for_files([str(target)], timeout=0.01)


def test_get_path_size_honors_cancellation(tmp_path):
    (tmp_path / "payload").write_bytes(b"payload")
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(CancelledError):
        FileUtils().get_path_size(tmp_path, human=False, cancel_event=cancel_event)
