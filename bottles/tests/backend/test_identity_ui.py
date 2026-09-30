from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bottles.backend import identity_ui


@pytest.mark.parametrize("fails", [False, True])
def test_server_exit_releases_application(monkeypatch, fails):
    stopped = Mock()
    application = SimpleNamespace(_server_stopped=stopped)
    server = Mock()
    idle_add = Mock()
    monkeypatch.setattr(identity_ui.GLib, "idle_add", idle_add)
    if fails:
        server.serve.side_effect = OSError("socket already in use")
        with pytest.raises(OSError):
            identity_ui.IdentityBridgeApplication._serve(application, server)
    else:
        identity_ui.IdentityBridgeApplication._serve(application, server)

    server.serve.assert_called_once_with()
    idle_add.assert_called_once_with(stopped)
