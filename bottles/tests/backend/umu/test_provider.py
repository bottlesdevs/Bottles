from pathlib import Path
from types import SimpleNamespace

import pytest

from bottles.backend.umu import UmuProvider, UmuProviderError
from bottles.backend.umu import provider as provider_module


def _launcher(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o755)
    return path


def _version_result(version="1.4.4"):
    return SimpleNamespace(
        returncode=0,
        stdout=f"umu-launcher version {version} (Python 3.13)\n",
        stderr="",
    )


def test_provider_prefers_explicit_launcher(monkeypatch, tmp_path):
    explicit = _launcher(tmp_path / "explicit" / "umu-run")
    fallback = _launcher(tmp_path / "fallback" / "umu-run")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: fallback)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return _version_result()

    monkeypatch.setattr(provider_module.subprocess, "run", run)

    installation = UmuProvider(explicit_path=explicit, fallback_path=fallback).resolve()

    assert installation.path == explicit.resolve()
    assert installation.source == "explicit"
    assert installation.version == "1.4.4"
    assert calls[0][0] == [str(explicit.resolve()), "--version"]
    assert calls[0][1]["shell"] is False


def test_provider_uses_system_before_managed(monkeypatch, tmp_path):
    system = _launcher(tmp_path / "system" / "umu-run")
    fallback = _launcher(tmp_path / "fallback" / "umu-run")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: str(system))
    monkeypatch.setattr(
        provider_module.subprocess, "run", lambda *_args, **_kwargs: _version_result()
    )

    installation = UmuProvider(fallback_path=fallback).resolve()

    assert installation.path == system.resolve()
    assert installation.source == "system"


def test_provider_falls_back_to_managed_launcher(monkeypatch, tmp_path):
    fallback = _launcher(tmp_path / "fallback" / "umu-run")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        provider_module.subprocess, "run", lambda *_args, **_kwargs: _version_result()
    )

    installation = UmuProvider(bundled_path=None, fallback_path=fallback).resolve()

    assert installation.path == fallback.resolve()
    assert installation.source == "managed"


def test_provider_classifies_path_bundled_launcher(monkeypatch, tmp_path):
    bundled = _launcher(tmp_path / "app" / "bin" / "umu-run")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: str(bundled))
    monkeypatch.setattr(
        provider_module.subprocess, "run", lambda *_args, **_kwargs: _version_result()
    )

    installation = UmuProvider(
        bundled_path=bundled, fallback_path=tmp_path / "managed" / "umu-run"
    ).resolve()

    assert installation.path == bundled.resolve()
    assert installation.source == "bundled"


def test_provider_does_not_hide_invalid_explicit_launcher(monkeypatch, tmp_path):
    explicit = _launcher(tmp_path / "explicit" / "umu-run")
    fallback = _launcher(tmp_path / "fallback" / "umu-run")
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: str(fallback))
    monkeypatch.setattr(
        provider_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="broken"
        ),
    )

    with pytest.raises(UmuProviderError, match="Invalid UMU launcher"):
        UmuProvider(explicit_path=explicit, fallback_path=fallback).resolve()


def test_provider_rejects_non_executable_launcher(tmp_path):
    launcher = tmp_path / "umu-run"
    launcher.touch()
    launcher.chmod(0o644)

    with pytest.raises(UmuProviderError, match="not executable"):
        UmuProvider(explicit_path=launcher).resolve()


def test_provider_reports_missing_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_module.shutil, "which", lambda _name: None)

    with pytest.raises(UmuProviderError, match="No usable UMU launcher"):
        UmuProvider(fallback_path=tmp_path / "missing").resolve()


def test_provider_executes_relative_candidate_by_absolute_path(monkeypatch, tmp_path):
    launcher = _launcher(tmp_path / "relative" / "umu-run")
    monkeypatch.chdir(tmp_path)
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return _version_result()

    monkeypatch.setattr(provider_module.subprocess, "run", run)

    installation = UmuProvider(explicit_path="relative/umu-run").resolve()

    assert installation.path == launcher.resolve()
    assert calls == [[str(launcher.resolve()), "--version"]]
