import shlex
from typing import Optional

import pytest

from bottles.backend.utils import generic
from bottles.backend.utils.generic import detect_encoding, is_ntsync_available


# CP932 is superset of Shift-JIS, which is default codec for Japanese in Windows
# GBK is default codec for Chinese in Windows
@pytest.mark.parametrize(
    "text, hint, codec",
    [
        ("Hello, world!", None, "ascii"),
        ("   ", None, "ascii"),
        ("Привет, мир!", None, "windows-1251"),
        ("こんにちは、世界！", "ja_JP", "cp932"),
        ("こんにちは、世界！", "ja_JP.utf-8", "utf-8"),
        ("你好，世界！", "zh_CN", "gbk"),
        ("你好，世界！", "zh_CN.UTF-8", "utf-8"),
        ("你好，世界！", "zh_CN.invalid_fallback", "gbk"),
        ("", None, "utf-8"),
    ],
)
def test_detect_encoding(text: str, hint: Optional[str], codec: Optional[str]):
    text_bytes = text.encode(codec)
    guess = detect_encoding(text_bytes, hint)
    assert guess.lower() == codec.lower()


def test_ntsync_requires_kernel_device(monkeypatch, tmp_path):
    runner = tmp_path / "runner" / "bin"
    runner.mkdir(parents=True)
    (runner / "wineserver").write_bytes(b"compiled with /dev/ntsync support")
    monkeypatch.setattr(generic, "NTSYNC_DEVICE", str(tmp_path / "missing"))

    assert not is_ntsync_available(str(runner / "wine"))


def test_ntsync_rejects_runner_without_compiled_support(monkeypatch, tmp_path):
    device = tmp_path / "ntsync"
    device.touch()
    runner = tmp_path / "wine-11.0" / "bin"
    runner.mkdir(parents=True)
    (runner / "wineserver").write_bytes(b"regular wineserver")
    monkeypatch.setattr(generic, "NTSYNC_DEVICE", str(device))

    assert not is_ntsync_available(str(runner / "wine"))


def test_ntsync_accepts_backported_runner_with_spaces(monkeypatch, tmp_path):
    device = tmp_path / "ntsync"
    device.touch()
    runner = tmp_path / "custom runner 9" / "bin"
    runner.mkdir(parents=True)
    (runner / "wineserver").write_bytes(b"prefix /dev/ntsync suffix")
    monkeypatch.setattr(generic, "NTSYNC_DEVICE", str(device))

    assert is_ntsync_available(shlex.quote(str(runner / "wine")))
