import shutil
import subprocess
from types import SimpleNamespace

import pytest

from bottles.backend.managers import eagle as eagle_module
from bottles.backend.managers.eagle import EagleManager
from bottles.backend.models.config import BottleConfig


@pytest.mark.parametrize("architecture", ["i686", "x86_64"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
@pytest.mark.parametrize("level", ["asInvoker", "requireAdministrator"])
@pytest.mark.parametrize("legacy,modern,aware", [
    (None, None, False), ("true", None, True), ("false", None, False),
    ("true/pm", None, True), (None, "PerMonitorV2", True),
    ("true", "unaware", False), ("false", "unknown, system", True),
])
def test_legacy_manifest_execution_level(monkeypatch, tmp_path, architecture, encoding, level, legacy, modern, aware):
    compiler = shutil.which(f"{architecture}-w64-mingw32-gcc")
    windres = shutil.which(f"{architecture}-w64-mingw32-windres")
    if not compiler or not windres:
        pytest.skip("MinGW compiler and resource compiler required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    manifest = tmp_path / "app.manifest"
    settings = '<application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>'
    if legacy is not None:
        settings += f'<dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">{legacy}</dpiAware>'
    if modern is not None:
        settings += f'<dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">{modern}</dpiAwareness>'
    settings += '</windowsSettings></application>'
    manifest.write_text('<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">'
        '<!-- requireAdministrator is mentioned here, not requested. -->'
        '<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges>'
        f'<requestedExecutionLevel level="{level}" uiAccess="false"/>'
        '</requestedPrivileges></security></trustInfo>' + settings + '</assembly>', encoding=encoding)
    resource = tmp_path / "app.rc"
    resource.write_text('1 24 "app.manifest"\n')
    obj = tmp_path / "app.o"
    target = tmp_path / "app.exe"
    subprocess.run([windres, str(resource), str(obj)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run([compiler, str(source), str(obj), "-o", str(target)], check=True, capture_output=True)
    manager = EagleManager.__new__(EagleManager)
    manager.config = BottleConfig(Runner="sys-wine")
    manager._yara_rules = None
    events = []
    manager._send_step = lambda *_args, **_kwargs: None
    manager._send = lambda kind, result: events.append((kind, result))
    monkeypatch.setattr(eagle_module, "EagleIntel", lambda: SimpleNamespace(available=False))
    manager.analyze(str(target))
    assert len(events) == 1
    assert events[0][0] == eagle_module.Signals.EagleFinished
    assert events[0][1].status
    assert events[0][1].data["admin"] is (level == "requireAdministrator")

    suggestions = events[0][1].data["suggestions"]
    assert any(item["key"] == "virtual_desktop" for item in suggestions) is not aware
