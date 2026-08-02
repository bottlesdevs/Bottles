from threading import Event

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager


@pytest.mark.parametrize("sandbox", [False, True])
def test_create_bottle_applies_sandbox_before_wineboot(monkeypatch, tmp_path, sandbox):
    captured = {}
    cancel_event = Event()

    class WineBoot:
        def __init__(self, config):
            captured["config"] = config

        def init(self):
            cancel_event.set()

    manager = object.__new__(Manager)
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: None,
    )
    monkeypatch.setattr(manager_module, "Reg", lambda _config: object())
    monkeypatch.setattr(manager_module, "RegKeys", lambda _config: object())
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)
    monkeypatch.setattr(manager_module, "WineServer", lambda _config: object())

    result = Manager.create_bottle(
        manager,
        name="Sandboxed",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
        sandbox=sandbox,
        cancel_event=cancel_event,
    )

    assert result.ok is False
    assert captured["config"].Parameters.sandbox is sandbox
    assert "XMODIFIERS" in captured["config"].Inherited_Environment_Variables
