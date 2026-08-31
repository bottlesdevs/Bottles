import json
import os
import time

from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.adaptive import (
    AdaptiveLaunchProfile,
    is_supported_runner,
    is_v2_runner,
)


def test_adaptive_launch_only_supports_soda():
    assert is_supported_runner("soda-11.0-5")
    assert is_supported_runner("soda-11.1-1")
    assert is_supported_runner("soda-12.0-1")
    assert not is_supported_runner("soda-11.0-4")
    assert not is_supported_runner("Soda")
    assert not is_supported_runner("protosoda-11.0-1")
    assert not is_supported_runner("wine-ge-8-26")


def test_adaptive_launch_v2_starts_with_soda_11_0_7():
    assert not is_v2_runner("soda-11.0-6")
    assert is_v2_runner("soda-11.0-7")
    assert is_v2_runner("soda-12.0-1")
    assert not is_v2_runner("protosoda-11.0-1")
    assert is_v2_runner("protosoda-11.0-2")
    assert not is_v2_runner("wine-ge-8-26")


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


def test_adaptive_v2_learns_an_old_trace(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    first = tmp_path / "first.dll"
    second = tmp_path / "second.dll"
    executable.write_bytes(b"MZ")
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    trace_dir = profile.traces / "finished"
    trace_dir.mkdir(parents=True)
    trace = trace_dir / "42.trace"
    trace.write_bytes(
        b"SODAAL2\0"
        + os.fsencode(str(first))
        + b"\0"
        + os.fsencode(str(second))
        + b"\0"
    )
    finished = time.time() - 61
    os.utime(trace, (finished, finished))
    os.utime(trace_dir, (finished, finished))
    calls = []
    monkeypatch.setattr(os, "posix_fadvise", lambda *args: calls.append(args))

    assert profile.prepare() == 2
    assert len(calls) == 2
    assert not trace_dir.exists()
    assert profile.trace_dir.is_dir()
    data = json.loads(profile.path.read_text())
    assert data["version"] == 2
    assert data["runner"] == "soda-11.0-7"
    assert data["sessions"] == [
        {"created": int(finished), "paths": [str(first), str(second)]}
    ]


def test_adaptive_v2_keeps_a_trace_that_may_still_be_written(tmp_path):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    library = tmp_path / "module.dll"
    executable.write_bytes(b"MZ")
    library.write_bytes(b"dll")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    trace_dir = profile.traces / "running"
    trace_dir.mkdir(parents=True)
    (trace_dir / "42.trace").write_bytes(
        b"SODAAL2\0" + os.fsencode(str(library)) + b"\0"
    )

    assert profile.prepare() == 0
    assert trace_dir.is_dir()
    assert json.loads(profile.path.read_text())["sessions"] == []


def test_adaptive_v2_discards_a_finished_corrupt_trace(tmp_path):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    executable.write_bytes(b"MZ")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    trace_dir = profile.traces / "corrupt"
    trace_dir.mkdir(parents=True)
    trace = trace_dir / "42.trace"
    trace.write_bytes(b"invalid")
    finished = time.time() - 61
    os.utime(trace, (finished, finished))
    os.utime(trace_dir, (finished, finished))

    assert profile.prepare() == 0
    assert not trace_dir.exists()
    assert json.loads(profile.path.read_text())["sessions"] == []


def test_adaptive_v2_profile_isolated_by_runner(tmp_path):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    executable.write_bytes(b"MZ")
    first = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    second = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    first.Runner = "soda-11.0-7"
    second.Runner = "soda-11.0-8"

    first_profile = AdaptiveLaunchProfile(first, str(executable))
    second_profile = AdaptiveLaunchProfile(second, str(executable))

    assert first_profile.path != second_profile.path


def test_adaptive_v2_ranks_frequency_position_and_recency():
    sessions = [
        {"created": 1, "paths": ["/old", "/shared"]},
        {"created": 2, "paths": ["/new", "/shared"]},
    ]

    assert AdaptiveLaunchProfile._rank_paths(sessions) == [
        "/shared",
        "/new",
        "/old",
    ]


def test_adaptive_v2_migrates_the_legacy_profile_once(tmp_path):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    library = tmp_path / "module.dll"
    executable.write_bytes(b"MZ")
    library.write_bytes(b"dll")
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    profile.legacy_path.parent.mkdir(parents=True)
    profile.legacy_path.write_bytes(os.fsencode(str(library)) + b"\0")

    assert profile.prepare() == 1
    first = json.loads(profile.path.read_text())
    assert first["legacy_migrated"] is True
    assert first["sessions"] == [{"created": 0, "paths": [str(library)]}]

    assert profile.prepare() == 1
    second = json.loads(profile.path.read_text())
    assert second["sessions"] == first["sessions"]


def test_adaptive_v2_does_not_prefetch_symlinks(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    library = tmp_path / "module.dll"
    link = tmp_path / "linked.dll"
    executable.write_bytes(b"MZ")
    library.write_bytes(b"dll")
    link.symlink_to(library)
    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    profile.legacy_path.parent.mkdir(parents=True)
    profile.legacy_path.write_bytes(os.fsencode(str(link)) + b"\0")
    calls = []
    monkeypatch.setattr(os, "posix_fadvise", lambda *args: calls.append(args))

    assert profile.prepare() == 0
    assert calls == []


def test_adaptive_v2_preserves_non_utf8_paths(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    executable = tmp_path / "game.exe"
    executable.write_bytes(b"MZ")
    raw_library = os.fsencode(tmp_path) + b"/module-\xff.dll"
    fd = os.open(raw_library, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.write(fd, b"dll")
    finally:
        os.close(fd)

    config = BottleConfig(Path=str(bottle), Custom_Path=str(bottle))
    config.Runner = "soda-11.0-7"
    profile = AdaptiveLaunchProfile(config, str(executable))
    trace_dir = profile.traces / "finished"
    trace_dir.mkdir(parents=True)
    trace = trace_dir / "42.trace"
    trace.write_bytes(b"SODAAL2\0" + raw_library + b"\0")
    finished = time.time() - 61
    os.utime(trace, (finished, finished))
    os.utime(trace_dir, (finished, finished))
    monkeypatch.setattr(os, "posix_fadvise", lambda *_args: None)

    assert profile.prepare() == 1
    data = json.loads(profile.path.read_text())
    assert data["sessions"][0]["paths"] == [os.fsdecode(raw_library)]
