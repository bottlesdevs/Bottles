"""Unit tests for WineExecutor placeholder handling"""

from bottles.backend.models.config import BottleConfig, BottleParams
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winecommand import WineCommand, WineEnv


def _make_config(name: str = "TestBottle", path: str = "TestBottlePath") -> BottleConfig:
    return BottleConfig(Name=name, Path=path, Custom_Path="", Environment="Custom")


def test_build_placeholder_map_uses_program_values():
    config = _make_config()
    program = {
        "name": "My Game",
        "path": "/opt/games/my-game.exe",
    }

    placeholders = WineExecutor._build_placeholder_map(config, program)

    expected_bottle_path = ManagerUtils.get_bottle_path(config)
    assert placeholders["PROGRAM_NAME"] == "My Game"
    assert placeholders["PROGRAM_PATH"] == "/opt/games/my-game.exe"
    assert placeholders["PROGRAM_DIR"] == "/opt/games"
    assert placeholders["BOTTLE_NAME"] == "TestBottle"
    assert placeholders["BOTTLE_PATH"] == expected_bottle_path


def test_replace_placeholders_handles_unknown_tokens():
    placeholders = {"PROGRAM_NAME": "Example", "BOTTLE_NAME": "Bottle"}

    result = WineExecutor._replace_placeholders(
        "run-%PROGRAM_NAME%-on-%BOTTLE_NAME%-%UNKNOWN%",
        placeholders,
    )

    assert result == "run-Example-on-Bottle-%UNKNOWN%"


def test_run_program_substitutes_placeholders(monkeypatch):
    captured: dict[str, object] = {}

    def fake_init(
        self,
        *,
        config,
        exec_path,
        args="",
        terminal=False,
        environment=None,
        move_file=False,
        move_upd_fn=None,
        pre_script=None,
        post_script=None,
        pre_script_args=None,
        post_script_args=None,
        cwd=None,
        monitoring=None,
        program_dxvk=None,
        program_vkd3d=None,
        program_nvapi=None,
        program_fsr=None,
        program_gamescope=None,
        program_virt_desktop=None,
        program_winebridge=None,
    ):
        # mimic original __init__ contract enough for run() stub
        self.config = config
        self.captured = {
            "exec_path": exec_path,
            "args": args,
            "pre_script": pre_script,
            "post_script": post_script,
            "pre_script_args": pre_script_args,
            "post_script_args": post_script_args,
            "cwd": cwd,
        }

    def fake_run(self):
        return Result(True, data=self.captured)

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(WineExecutor, "run", fake_run, raising=False)

    config = _make_config(name="Bottle", path="BottlePath")
    program = {
        "name": "Awesome Game",
        "path": "/games/awesome/game.exe",
        "arguments": "--title=%PROGRAM_NAME%",
        "pre_script": "/scripts/%BOTTLE_NAME%/%PROGRAM_NAME%.sh",
        "pre_script_args": "--prefix=%BOTTLE_PATH%",
        "post_script": None,
        "post_script_args": "--dir=%PROGRAM_DIR%",
        "folder": "%PROGRAM_DIR%",
    }

    result = WineExecutor.run_program(config=config, program=program, terminal=False)

    assert result.status is True
    data = result.data
    assert data["exec_path"] == "/games/awesome/game.exe"
    assert data["args"] == "--title=Awesome Game"
    assert data["pre_script"] == "/scripts/Bottle/Awesome Game.sh"
    assert data["pre_script_args"] == f"--prefix={ManagerUtils.get_bottle_path(config)}"
    assert data["post_script_args"] == "--dir=/games/awesome"
    assert data["cwd"] == "/games/awesome"


def test_wine_env_respects_allowed_keys(monkeypatch):
    monkeypatch.setenv("KEEP_ONLY", "1")
    monkeypatch.setenv("DROP_ME", "2")

    env = WineEnv(clean=False, allowed_keys=["KEEP_ONLY"])
    resolved = env.get()["envs"]

    assert resolved["KEEP_ONLY"] == "1"
    assert "DROP_ME" not in resolved


def test_winecommand_filters_host_environment(monkeypatch, tmp_path):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    runner_path = tmp_path / "runner"
    for sub in [
        "lib",
        "lib64",
        "lib/wine/x86_64-unix",
        "lib32/wine/x86_64-unix",
        "lib32",
        "lib64/wine/x86_64-unix",
        "lib/wine/i386-unix",
        "lib32/wine/i386-unix",
        "lib64/wine/i386-unix",
    ]:
        (runner_path / sub).mkdir(parents=True, exist_ok=True)

    config = BottleConfig(Name="Test", Path=str(bottle_path), Runner="test")
    params = BottleParams()
    params.use_runtime = False
    params.use_eac_runtime = False
    params.use_be_runtime = False
    config.Parameters = params
    config.Limit_System_Environment = True
    config.Inherited_Environment_Variables = ["DISPLAY"]

    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("SHOULD_NOT_PASS", "secret")

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: str(runner_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.SteamUtils.is_proton", lambda *_: False
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.check_nvidia_device",
        lambda: None,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.display_server_type",
        lambda: "x11",
    )

    def _fake_gpu(self):
        return {
            "prime": {
                "discrete": None,
                "integrated": {"icd": "/tmp/icd", "envs": {}},
            },
            "vendors": {"generic": {"icd": "/tmp/icd", "envs": {}}},
        }

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.GPUUtils.get_gpu",
        _fake_gpu,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.RuntimeManager.get_runtime_env",
        lambda *_: [],
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = True
    winecmd.arguments = ""
    winecmd.runner = "/usr/bin/wine"
    winecmd.runner_runtime = ""
    winecmd.gamescope_activated = False
    winecmd.terminal = False

    env = winecmd.get_env()
    assert env["DISPLAY"] == ":1"
    assert "SHOULD_NOT_PASS" not in env
