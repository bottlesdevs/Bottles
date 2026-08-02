from types import SimpleNamespace

from bottles.backend.managers.backup import BackupManager
from bottles.backend.models.config import BottleConfig, BottleParams
from bottles.backend.utils.lsfgvk import get_lsfg_vk_dll_path
from bottles.backend.wine.winecommand import WineEnv, apply_lsfg_vk_preferences


def _apply(params, bottle_path, version=1):
    env = WineEnv(clean=True)
    apply_lsfg_vk_preferences(env, params, str(bottle_path), version)
    return env.get()["envs"]


def _create_dll(bottle_path):
    dll = get_lsfg_vk_dll_path(str(bottle_path))
    bottle_path.joinpath("lsfg-vk").mkdir(parents=True)
    bottle_path.joinpath("lsfg-vk", "Lossless.dll").write_bytes(b"MZ")
    return dll


def test_disabled_lsfg_vk_preserves_external_layer_configuration(tmp_path):
    env = _apply(BottleParams(), tmp_path)

    assert env == {}


def test_lsfg_vk_requires_an_available_layer(tmp_path):
    _create_dll(tmp_path)
    params = BottleParams(lsfg_vk=True)

    env = _apply(params, tmp_path, version=0)

    assert env == {
        "DISABLE_LSFG": "1",
        "DISABLE_LSFGVK": "1",
    }


def test_lsfg_vk_requires_a_readable_dll(tmp_path):
    env = _apply(BottleParams(lsfg_vk=True), tmp_path)

    assert env == {
        "DISABLE_LSFG": "1",
        "DISABLE_LSFGVK": "1",
    }


def test_lsfg_vk_rejects_invalid_frame_settings(tmp_path):
    _create_dll(tmp_path)
    params = BottleParams(
        lsfg_vk=True,
        lsfg_vk_multiplier=1,
        lsfg_vk_flow_scale=2,
    )

    env = _apply(params, tmp_path)

    assert env == {
        "DISABLE_LSFG": "1",
        "DISABLE_LSFGVK": "1",
    }


def test_lsfg_vk_sets_stable_environment(tmp_path):
    dll = _create_dll(tmp_path)
    params = BottleParams(
        lsfg_vk=True,
        lsfg_vk_multiplier=3,
        lsfg_vk_flow_scale=0.7,
        lsfg_vk_performance_mode=True,
    )

    env = _apply(params, tmp_path, version=1)

    assert env == {
        "DISABLE_LSFGVK": "1",
        "LSFG_LEGACY": "1",
        "LSFG_DLL_PATH": dll,
        "LSFG_MULTIPLIER": "3",
        "LSFG_FLOW_SCALE": "0.7",
        "LSFG_PERFORMANCE_MODE": "1",
    }


def test_lsfg_vk_sets_version_two_environment(tmp_path):
    dll = _create_dll(tmp_path)
    params = BottleParams(
        lsfg_vk=True,
        lsfg_vk_multiplier=3,
        lsfg_vk_flow_scale=0.7,
        lsfg_vk_performance_mode=True,
    )

    env = _apply(params, tmp_path, version=2)

    assert env == {
        "DISABLE_LSFG": "1",
        "LSFGVK_ENV": "1",
        "LSFGVK_DLL_PATH": dll,
        "LSFGVK_MULTIPLIER": "3",
        "LSFGVK_FLOW_SCALE": "0.7",
        "LSFGVK_PERFORMANCE_MODE": "1",
    }


def test_lsfg_vk_settings_round_trip_through_bottle_config(tmp_path):
    config_path = tmp_path / "bottle.yml"
    config = BottleConfig()
    config.Parameters.lsfg_vk = True
    config.Parameters.lsfg_vk_multiplier = 4
    config.Parameters.lsfg_vk_flow_scale = 0.65
    config.Parameters.lsfg_vk_performance_mode = True

    assert config.dump(str(config_path)).status is True
    loaded = BottleConfig.load(str(config_path))

    assert loaded.status is True
    assert loaded.data.Parameters.lsfg_vk is True
    assert loaded.data.Parameters.lsfg_vk_multiplier == 4
    assert loaded.data.Parameters.lsfg_vk_flow_scale == 0.65
    assert loaded.data.Parameters.lsfg_vk_performance_mode is True
    assert "lsfg_vk_dll" not in config_path.read_text()


def test_lsfg_vk_dll_is_excluded_from_full_backups():
    directory = SimpleNamespace(name="Bottle/lsfg-vk")
    dll = SimpleNamespace(name="Bottle/lsfg-vk/Lossless.dll")
    regular = SimpleNamespace(name="Bottle/drive_c/game.exe")

    assert BackupManager.exclude_filter(directory) is None
    assert BackupManager.exclude_filter(dll) is None
    assert BackupManager.exclude_filter(regular) is regular
