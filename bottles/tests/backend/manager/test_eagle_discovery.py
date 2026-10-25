import shutil
import subprocess
import struct
from types import SimpleNamespace

import pytest

from bottles.backend.managers import eagle as eagle_module
from bottles.backend.managers.eagle import EagleManager
from bottles.backend.models.config import BottleConfig


@pytest.mark.parametrize("architecture,expected", [("i686", "x86 (32-bit)"), ("x86_64", "x86_64 (64-bit)")])
@pytest.mark.parametrize("kind", ["file", "directory", "broken-link", "file-link"])
def test_unreal_shipping_candidate(monkeypatch, tmp_path, architecture, expected, kind):
    compiler = shutil.which(f"{architecture}-w64-mingw32-gcc")
    if not compiler:
        pytest.skip("MinGW required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    target = tmp_path / "launcher.exe"
    subprocess.run([compiler, str(source), "-o", str(target)], check=True, capture_output=True)
    (tmp_path / "Engine").mkdir()
    shipping = tmp_path / "Game/Binaries/Win64/Game-Win64-Shipping.exe"
    shipping.parent.mkdir(parents=True)
    if kind == "file":
        shutil.copyfile(target, shipping)
    elif kind == "directory":
        shipping.mkdir()
    else:
        shipping.symlink_to(target if kind == "file-link" else tmp_path / "missing.exe")
    manager = EagleManager.__new__(EagleManager)
    manager.config = BottleConfig(Runner="sys-wine")
    manager._yara_rules = None
    steps = []
    manager._send_step = lambda message, **_kwargs: steps.append(message)
    events = []
    manager._send = lambda kind, result: events.append((kind, result))
    monkeypatch.setattr(eagle_module, "STEP_DELAY", 0)
    monkeypatch.setattr(eagle_module, "EagleIntel", lambda: SimpleNamespace(available=False))
    monkeypatch.setattr(eagle_module, "Gio", SimpleNamespace(Settings=SimpleNamespace(
        new=lambda _app: SimpleNamespace(get_int=lambda _key: 20))))
    manager.analyze(str(target))
    assert events[-1][1].status
    report = events[-1][1].data
    assert report["arch"] == expected
    assert "[!] Unreal Engine bootstrapper detected - searching for shipping binary..." in steps
    messages = [item for item in report["messages"] if item["name"] == "Unreal Engine Bootstrapper"]
    assert bool(messages) is (kind in ("file", "file-link"))
    if messages:
        assert messages[0]["context"] == [str(shipping)]


@pytest.mark.parametrize("mono", [False, True])
def test_runtime_suggestion_order(monkeypatch, tmp_path, mono):
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        pytest.skip("MinGW required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    target = tmp_path / "app.exe"
    subprocess.run([compiler, str(source), "-o", str(target)], check=True, capture_output=True)
    manager = EagleManager.__new__(EagleManager)
    manager.config = BottleConfig(Runner="sys-wine")
    manager._yara_rules = None
    manager._send_step = lambda *_args, **_kwargs: None
    runtimes = [".NET Framework", "VC++ 2019", ".NET Core/5+", "VC++ 2015", ".NET Framework"]
    if mono:
        runtimes.append("Mono")
    manager._scan_yara = lambda _path, insights: insights["Runtimes"].extend(runtimes) or []
    events = []
    manager._send = lambda kind, result: events.append(result)
    monkeypatch.setattr(eagle_module, "EagleIntel", lambda: SimpleNamespace(available=False))
    monkeypatch.setattr(eagle_module, "Gio", SimpleNamespace(Settings=SimpleNamespace(
        new=lambda _app: SimpleNamespace(get_int=lambda _key: 20))))
    manager.analyze(str(target))
    assert events[-1].status
    suggestions = events[-1].data["suggestions"]
    suffix = " (Try Mono first)" if mono else ""
    assert [item["label"] for item in suggestions if item["key"] == "dep_dotnet"] == [
        ".NET Core/5+" + suffix, ".NET Framework" + suffix]
    assert [item["label"] for item in suggestions if item["key"] == "dep_vcredist"] == [
        "Visual C++ (VC++ 2015, VC++ 2019)"]


@pytest.mark.parametrize("product,count,expected", [
    (0x104, 42, "Microsoft tools (linker 14.44)"), (0x9999, 0x1040000, None)])
def test_rich_tool_records(monkeypatch, tmp_path, product, count, expected):
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        pytest.skip("MinGW required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    target = tmp_path / "app.exe"
    subprocess.run([compiler, str(source), "-o", str(target)], check=True, capture_output=True)
    data = bytearray(target.read_bytes())
    assert struct.unpack_from("<I", data, 0x3c)[0] >= 0x80
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    optional = pe + 24
    table = optional + struct.unpack_from("<H", data, pe + 20)[0]
    end = table + 40 * struct.unpack_from("<H", data, pe + 6)[0]
    assert end + 32 <= struct.unpack_from("<I", data, optional + 60)[0]
    data[pe + 32:end + 32] = bytes(data[pe:end])
    struct.pack_into("<I", data, 0x3c, pe + 32)
    key = 0x12345678
    data[0x80:0xa0] = struct.pack("<8I", 0x536e6144 ^ key, key, key, key,
        ((product << 16) | 35229) ^ key, count ^ key, 0x68636952, key)
    optional = struct.unpack_from("<I", data, 0x3c)[0] + 24
    data[optional + 2:optional + 4] = bytes((14, 44))
    target.write_bytes(data)
    manager = EagleManager.__new__(EagleManager)
    manager.config = BottleConfig(Runner="sys-wine")
    manager._yara_rules = None
    manager._send_step = lambda *_args, **_kwargs: None
    events = []
    manager._send = lambda kind, result: events.append(result)
    monkeypatch.setattr(eagle_module, "EagleIntel", lambda: SimpleNamespace(available=False))
    monkeypatch.setattr(eagle_module, "Gio", SimpleNamespace(Settings=SimpleNamespace(
        new=lambda _app: SimpleNamespace(get_int=lambda _key: 20))))
    manager.analyze(str(target))
    assert events[-1].status
    assert events[-1].data["metadata"]["compiler"] == expected
