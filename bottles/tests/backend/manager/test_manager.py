"""Core Manager tests"""
from bottles.backend.managers.manager import Manager


def test_manager_is_singleton():
    assert Manager() is Manager()


def test_manager_default_gsettings_stub():
    assert Manager().settings.get_boolean("anything") is False
