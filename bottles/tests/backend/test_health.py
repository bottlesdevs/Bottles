from bottles.backend.health import HealthChecker


def test_health_results_report_vulkan_support():
    checker = object.__new__(HealthChecker)
    checker.desktop = "GNOME"
    checker.x11 = False
    checker.x11_port = ""
    checker.wayland = True
    checker.gpus = {"vendors": {"amd": {}}}
    checker.vulkan = True
    checker.kernel = "Linux"
    checker.kernel_version = "6.0"
    checker.disk = {}
    checker.ram = {}
    checker.bottles_envs = {}

    results = checker.get_results()

    assert results["Graphics"]["Vulkan"] is True
    assert results["Graphics"]["vendors"] == {"amd": {}}
