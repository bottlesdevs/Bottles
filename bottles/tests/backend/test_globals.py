from pathlib import Path

from bottles.backend.globals import (
    Paths,
    _get_wine_compatible_base,
    _has_windows_unsafe_component,
    is_cpak,
    is_official_package,
)


def test_wine_compatible_base_keeps_unsafe_native_path(tmp_path, monkeypatch):
    base = tmp_path / "user." / "data" / "bottles"
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    assert _get_wine_compatible_base(str(base)) == str(base)


def test_wine_compatible_base_keeps_safe_path(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    base = tmp_path / "user" / "data" / "bottles"
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
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


def test_official_package_detection(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.delenv("CPAK_CONTAINER_ID", raising=False)
    assert not is_cpak()
    assert not is_official_package()

    monkeypatch.setenv("CPAK_CONTAINER_ID", "bottles")
    assert is_cpak()
    assert is_official_package()

    monkeypatch.delenv("CPAK_CONTAINER_ID")
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    assert is_official_package()


def test_lsfg_vk_detects_flatpak_extension(monkeypatch):
    expected = (
        "/usr/lib/extensions/vulkan/lsfgvk/share/vulkan/implicit_layer.d/"
        "VkLayer_LS_frame_generation.json"
    )
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isfile",
        lambda path: path == expected,
    )

    assert Paths.get_lsfg_vk_version() == 1


def test_lsfg_vk_detects_version_two_user_install(monkeypatch):
    expected = (
        f"{Paths.xdg_data_home}/vulkan/implicit_layer.d/"
        "VkLayer_LSFGVK_frame_generation.json"
    )
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isfile",
        lambda path: path == expected,
    )

    assert Paths.get_lsfg_vk_version() == 2


def test_lsfg_vk_prefers_version_two(monkeypatch):
    manifests = {
        "/usr/share/vulkan/implicit_layer.d/VkLayer_LS_frame_generation.json",
        "/etc/vulkan/implicit_layer.d/VkLayer_LSFGVK_frame_generation.json",
    }
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isfile",
        lambda path: path in manifests,
    )

    assert Paths.get_lsfg_vk_version() == 2


def test_lsfg_vk_detects_custom_layer_path(monkeypatch, tmp_path):
    layer_dir = tmp_path / "layers"
    expected = layer_dir / "VkLayer_LS_frame_generation.json"
    monkeypatch.setenv("VK_ADD_LAYER_PATH", str(layer_dir))
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isfile",
        lambda path: path == str(expected),
    )

    assert Paths.get_lsfg_vk_version() == 1


def test_lsfg_vk_is_unavailable_without_layer_manifest(monkeypatch):
    monkeypatch.setattr(
        "bottles.backend.globals.os.path.isfile",
        lambda _path: False,
    )

    assert Paths.get_lsfg_vk_version() == 0
