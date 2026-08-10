import os

from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.adaptive import AdaptiveLaunchProfile, is_supported_runner


def test_adaptive_launch_only_supports_soda():
    assert is_supported_runner("soda-11.0-5")
    assert is_supported_runner("soda-11.1-1")
    assert is_supported_runner("soda-12.0-1")
    assert not is_supported_runner("soda-11.0-4")
    assert not is_supported_runner("Soda")
    assert not is_supported_runner("protosoda-11.0-1")
    assert not is_supported_runner("wine-ge-8-26")


def test_adaptive_profile_prefetches_recorded_files(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    library = tmp_path / "module.dll"
    executable.write_bytes(b"MZ")
    library.write_bytes(b"dll")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    profile = AdaptiveLaunchProfile(config, str(executable))
    profile.path.parent.mkdir(parents=True)
    profile.path.write_bytes(
        os.fsencode(str(library)) + b"\0" + os.fsencode(str(library)) + b"\0"
    )
    calls = []
    monkeypatch.setattr(os, "posix_fadvise", lambda *args: calls.append(args))

    assert profile.prepare() == 1
    assert len(calls) == 1
    assert profile.path.read_bytes() == os.fsencode(str(library)) + b"\0"


def test_adaptive_profile_creates_an_empty_profile(tmp_path):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    executable.write_bytes(b"MZ")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    profile = AdaptiveLaunchProfile(config, str(executable))

    assert profile.prepare() == 0
    assert profile.path.read_bytes() == b""
