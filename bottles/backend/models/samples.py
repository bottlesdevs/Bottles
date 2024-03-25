class Samples:
    data = {}
    environments = {
        "gaming": {
            "Runner": "wine",
            "Parameters": {
                "dxvk": True,
                # "nvapi": True,
                "vkd3d": True,
                "sync": "fsync",
                "fsr": False,
                "discrete_gpu": True,
                "pulseaudio_latency": False,
            },
            "Installed_Dependencies": [
                "d3dx9",
                "msls31",
                "arial32",
                "times32",
                "courie32",
                "d3dcompiler_43",
                "d3dcompiler_47",
                "mono",
                "gecko",
            ],
        },
        "application": {
            "Runner": "wine",
            "Parameters": {"dxvk": True, "vkd3d": True, "pulseaudio_latency": False},
            "Installed_Dependencies": [
                "arial32",
                "times32",
                "courie32",
                "mono",
                "gecko",
                # "dotnet40",
                # "dotnet48"
            ],
        },
    }
    bottles_to_steam_relations = {
        "MANGOHUD": ("mangohud", True),
        "OBS_VKCAPTURE": ("obsvkc", True),
        "ENABLE_VKBASALT": ("vkbasalt", True),
        "WINEESYNC": ("sync", "esync"),
        "WINEFSYNC": ("sync", "fsync"),
        "WINE_FULLSCREEN_FSR": ("fsr", True),
        "WINE_FULLSCREEN_FSR_STRENGTH": ("fsr_sharpening_strength", 2),
        "WINE_FULLSCREEN_FSR_MODE": ("fsr_quality_mode", "none"),
        "DRI_PRIME": ("discrete_gpu", True),
        "__NV_PRIME_RENDER_OFFLOAD": ("discrete_gpu", True),
        "PULSE_LATENCY_MSEC": ("pulseaudio_latency", True),
        "PROTON_EAC_RUNTIME": ("use_eac_runtime", True),
        "PROTON_BATTLEYE_RUNTIME": ("use_be_runtime", True),
    }
