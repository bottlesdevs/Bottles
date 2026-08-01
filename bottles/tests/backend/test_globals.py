from pathlib import Path

from bottles.backend.globals import (
    _get_wine_compatible_base,
    _has_windows_unsafe_component,
)


def test_wine_compatible_base_keeps_unsafe_native_path(tmp_path, monkeypatch):
    base = tmp_path / "user." / "data" / "bottles"
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    assert _get_wine_compatible_base(str(base)) == str(base)


def test_wine_compatible_base_keeps_safe_path(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    base = tmp_path / "user" / "data" / "bottles"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))

    assert _get_wine_compatible_base(str(base)) == str(base)
    assert not runtime_dir.exists()


def test_wine_compatible_base_uses_flatpak_data_mount(tmp_path, monkeypatch):
    base = tmp_path / "user." / "data" / "bottles"
    data_home = base.parent
    data_home.mkdir(parents=True)
    original_isdir = Path.is_dir
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isdir",
        lambda path: path == "/var/data" or original_isdir(Path(path)),
    )
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.samefile",
        lambda first, second: first == str(data_home) and second == "/var/data",
    )

    assert _get_wine_compatible_base(str(base)) == "/var/data/bottles"


def test_windows_unsafe_component_detects_trailing_space():
    assert _has_windows_unsafe_component("/tmp/user /data/bottles")
