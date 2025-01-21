"""Core Manager tests"""

from bottles.backend.managers.manager import Manager
from bottles.backend.utils.gsettings_stub import GSettingsStub


def test_manager_is_singleton():
    assert Manager() is Manager(), "Manager should be singleton object"
    assert Manager() is Manager(
        g_settings=GSettingsStub()
    ), "Manager should be singleton even with different argument"


def test_manager_default_gsettings_stub():
    assert Manager().settings.get_boolean("anything") is False
