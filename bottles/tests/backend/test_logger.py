import logging

import pytest

from bottles.backend.logger import Logger


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    level = root.level
    handlers = root.handlers.copy()
    yield
    root.setLevel(level)
    root.handlers = handlers


@pytest.mark.parametrize(
    "value,expected",
    [
        ("debug", logging.DEBUG),
        ("unknown", logging.INFO),
    ],
)
def test_log_level_environment(monkeypatch, value, expected):
    monkeypatch.setenv("LOG_LEVEL", value)

    Logger()

    assert logging.getLogger().level == expected
