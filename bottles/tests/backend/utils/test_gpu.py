from bottles.backend.utils import gpu as gpu_module
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.vulkan import VulkanUtils


def test_vulkan_detects_nouveau_icds(monkeypatch, tmp_path):
    vulkan_dir = tmp_path / "vulkan"
    icd_dir = vulkan_dir / "icd.d"
    icd_dir.mkdir(parents=True)
    x86_64 = icd_dir / "nouveau_icd.x86_64.json"
    i686 = icd_dir / "nouveau_icd.i686.json"
    nvk = icd_dir / "nvk_icd.json"
    x86_64.touch()
    i686.touch()
    nvk.touch()

    monkeypatch.setattr(
        VulkanUtils,
        "_VulkanUtils__vk_icd_dirs",
        [str(vulkan_dir)],
    )

    assert set(VulkanUtils().get_vk_icd("nouveau")) == {
        str(x86_64),
        str(i686),
        str(nvk),
    }


def test_nouveau_detection_uses_sysfs_inside_flatpak(monkeypatch):
    monkeypatch.setattr(
        gpu_module.os.path,
        "isdir",
        lambda path: path == "/sys/module/nouveau",
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("lsmod should not be needed")

    monkeypatch.setattr(gpu_module.subprocess, "Popen", fail)

    assert GPUUtils.is_nouveau() is True


def test_nouveau_gpu_uses_nvk_icd(monkeypatch):
    class FakeProcess:
        def __init__(self, command, **_kwargs):
            self.command = command

        def communicate(self):
            if "NVIDIA" in self.command:
                return b"01:00.0 VGA compatible controller: NVIDIA Corporation", b""
            return b"", b""

    monkeypatch.setattr(gpu_module.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(GPUUtils, "is_nouveau", lambda _self: True)
    monkeypatch.setattr(gpu_module, "get_nvidia_dll_path", lambda: None)

    gpu = GPUUtils()
    monkeypatch.setattr(
        gpu.vk,
        "get_vk_icd",
        lambda vendor, as_string=False: f"/{vendor}.json",
    )

    nvidia = gpu.get_gpu()["vendors"]["nvidia"]

    assert nvidia["envs"] == {"DRI_PRIME": "1"}
    assert nvidia["icd"] == "/nouveau.json"


def test_nvidia_gpu_falls_back_to_available_nvk_icd(monkeypatch):
    class FakeProcess:
        def __init__(self, command, **_kwargs):
            self.command = command

        def communicate(self):
            if "NVIDIA" in self.command:
                return b"01:00.0 VGA compatible controller: NVIDIA Corporation", b""
            return b"", b""

    monkeypatch.setattr(gpu_module.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(GPUUtils, "is_nouveau", lambda _self: False)
    monkeypatch.setattr(gpu_module, "get_nvidia_dll_path", lambda: None)

    gpu = GPUUtils()
    monkeypatch.setattr(
        gpu.vk,
        "get_vk_icd",
        lambda vendor, as_string=False: (
            "/nouveau_icd.x86_64.json" if vendor == "nouveau" else ""
        ),
    )

    nvidia = gpu.get_gpu()["vendors"]["nvidia"]

    assert nvidia["envs"] == {"DRI_PRIME": "1"}
    assert nvidia["icd"] == "/nouveau_icd.x86_64.json"
