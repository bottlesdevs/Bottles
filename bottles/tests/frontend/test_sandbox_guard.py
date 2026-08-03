from types import SimpleNamespace

from bottles.frontend.utils import sandbox_guard


def test_launch_resolves_accessible_portal_path(monkeypatch):
    portal_path = "/run/user/1000/doc/document-id/Game.exe"
    host_path = "/home/user/Games/Game/Game.exe"
    launches = []
    config = SimpleNamespace(Parameters=SimpleNamespace(sandbox=False))
    monkeypatch.setattr(
        sandbox_guard.ManagerUtils,
        "resolve_portal_path",
        lambda path: host_path if path == portal_path else path,
    )

    sandbox_guard.guard_sandbox_launch(
        object(), config, portal_path, lambda *args: launches.append(args)
    )

    assert launches == [(None, host_path)]
